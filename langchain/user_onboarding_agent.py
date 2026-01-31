import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from llm.llama import get_llm

import re
from typing import Any
from datetime import datetime, timezone
import sqlite3


def mcp_server_path() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "insurance_mcp.py")


async def setup_mcp_client():
    """Connect to MCP Server."""

    mcp_server_script = os.getenv("INSURANCE_MCP_SERVER", mcp_server_path())

    client = MultiServerMCPClient(
        {
            "insurance": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [mcp_server_script],
                "env": {
                    "MCP_TRANSPORT": "stdio",
                    "INSURANCE_DB_PATH": os.getenv(
                        "INSURANCE_DB_PATH", os.path.join("database", "insurance.db")
                    ),
                },
            }
        }
    )

    return await client.get_tools()


async def initialize_agent():
    llm = get_llm()
    tools = await setup_mcp_client()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=(
            "You are a helpful user onboarding assistant for an auto insurance learning app.\n"
            "Your job is to collect the user's profile id, name, age, state, vehicleName, coverageType and store it using the get_customer_info function.\n"
            "id must be an integer, name should be a string, age should be an integer, state should be a string, vehicleName should be a string, and coverageType should be a string.\n"
            "Always be polite and thorough in your responses.\n"
        ),
    )
    return agent


async def run_agent(agent, user_query: str):
    """
        Avoids dumping raw streaming chunks.
    """

    final_text: str | None = None

    try:
        async for chunk in agent.astream({
            "messages": [{"role": "user", "content": user_query}]
        }):
            if not isinstance(chunk, dict):
                continue

            messages = chunk.get("messages")
            if not messages:
                continue

            last = messages[-1]

            if isinstance(last, dict):
                if last.get("role") == "assistant" and last.get("content"):
                    final_text = last["content"]
            else:
                role = getattr(last, "type", None) or getattr(last, "role", None)
                content = getattr(last, "content", None)
                if role in {"ai", "assistant"} and content:
                    final_text = content
    except (asyncio.CancelledError, KeyboardInterrupt):
        # Don't crash the whole CLI if the user interrupts or the LLM stream gets cancelled.
        print("\n(LLM response cancelled. Your profile is still saved.)")
        return
    except Exception as e:
        print(
            "The onboarding agent couldn't reach the LLM backend.\n"
            "If you're using Ollama, make sure it's running and your model is available.\n"
            f"Details: {e}"
        )
        return

    if final_text:
        print(final_text)


async def onboard(onboarding_agent, user_query: str):
    """Persist onboarding immediately, then optionally let the LLM respond and plan curriculum."""

    def _parse_profile(text: str) -> dict[str, Any] | None:
        t = (text or "").strip()
        if not t:
            return None

        m_id = re.search(r"\b(?:my\s*)?id\s*is\s*(\d+)\b", t, flags=re.IGNORECASE)
        m_name = re.search(r"\bmy\s*name\s*is\s*([^,\.]+)", t, flags=re.IGNORECASE)
        m_age = re.search(r"\b(?:i\s*'?m|i\s*am)\s*(\d{1,3})\b", t, flags=re.IGNORECASE)
        m_state = re.search(r"\b(?:i\s*live\s*in|i\s*am\s*in|i\s*live\s*at)\s*([A-Za-z]{2})\b", t, flags=re.IGNORECASE)
        m_vehicle = re.search(r"\bmy\s*vehicle\s*(?:is|=)\s*([^,\.]+)", t, flags=re.IGNORECASE)
        m_cov = re.search(r"\bcoverage\s*type\s*(?:is|=)\s*([^,\.]+)", t, flags=re.IGNORECASE)

        if not (m_id and m_name and m_age and m_state and m_vehicle and m_cov):
            return None

        def _clean_vehicle(v: str) -> str:
            v0 = (v or "").strip()
            v0 = re.sub(r"^\s*(?:a|an|the)\s+", "", v0, flags=re.IGNORECASE)
            return v0.strip()

        customer_id = int(m_id.group(1))
        age = int(m_age.group(1))
        state = m_state.group(1).upper()
        return {
            "id": customer_id,
            "name": m_name.group(1).strip(),
            "age": age,
            "state": state,
            "vehicleName": _clean_vehicle(m_vehicle.group(1)),
            "coverageType": m_cov.group(1).strip(),
        }

    profile = _parse_profile(user_query)

    if profile is None:
        await run_agent(onboarding_agent, user_query)
        match = re.search(r"\b(\d+)\b", user_query)
        if not match:
            return
        customer_id = int(match.group(1))
    else:

        db_path = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))
        now = datetime.now(timezone.utc).strftime("%m/%d/%Y")

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    age=excluded.age,
                    state=excluded.state,
                    vehicle_name=excluded.vehicle_name,
                    coverage_type=excluded.coverage_type,
                    updated_at=excluded.updated_at;
                """,
                (
                    int(profile["id"]),
                    str(profile["name"]),
                    int(profile["age"]),
                    str(profile["state"]),
                    str(profile["vehicleName"]),
                    str(profile["coverageType"]),
                    now,
                    now,
                ),
            )

        customer_id = int(profile["id"])
        print(
            "Saved profile to database: "
            f"id={customer_id} | name={profile['name']} | age={profile['age']} | state={profile['state']}"
        )

        await run_agent(onboarding_agent, user_query)

    try:
        from langchain.curriculum_planner_agent import initialize_agent as init_curriculum_agent

        curriculum_agent = await init_curriculum_agent()
        await run_agent(curriculum_agent, f"Plan a curriculum for customer id {customer_id}")
    except Exception:
        return


async def chat():
    """
        A chat interface where users can enter their credentials for onboarding.
    """

    agent = await initialize_agent()

    print("Hello and welcome to Auto Insurance User Onboarding")
    print("Please type in your credentials and press Enter")
    print("Once you're done, type 'exit' to quit")
    print("Here is a sample message: ")
    print("Hey. My id is 2, my name is Samuel, I'm 16, I live in NY, my vehicle is a Toyota Camry, and my coverage type is full coverage.")
    print()

    while True:
        try:
            try:
                user_query = input("> ").strip()
            except EOFError:
                break

            if not user_query:
                continue
            if user_query.lower() in {"exit", "quit"}:
                break

            await onboard(agent, user_query)
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except asyncio.CancelledError:
            print("\nCancelled.")
            break


if __name__ == "__main__":
    asyncio.run(chat())