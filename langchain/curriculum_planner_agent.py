import asyncio
import os
import sys
from pathlib import Path
import argparse
from typing import Any
import re
import json

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from llm.llama import get_llm

def mcp_server_path() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "insurance_mcp.py")


async def setup_mcp_client():
    """Connect to MCP Server and return its tools."""

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
    """Create the Curriculum Planner Agent."""

    llm = get_llm()
    tools = await setup_mcp_client()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=(
            "You are the Curriculum Planner Agent for an auto insurance learning app.\n"
            "Your job is to create a personalized curriculum plan for a user.\n\n"
            "You have access to MCP tools:\n"
            "plan_curriculum(customer_id: int): creates and persists a curriculum plan for the customer_id\n"
            "get_curriculum(customer_id: int): returns the latest persisted curriculum\n\n"
            "Rules:\n"
            "1) Always ask for customer_id if missing.\n"
            "2) If the user asks to create, generate, or plan a curriculum, call plan_curriculum.\n"
            "3) If the user asks to view, show, or get the curriculum, call get_curriculum.\n"
            "4) Present results as a short ordered title list, then offer help to dive deeper.\n"
        ),
    )

    return agent


async def run_agent(agent, user_query: str):
    """Run a single user query and print final assistant output.

    To reduce latency (and avoid slow streaming hangs), this uses a single `ainvoke`
    call with a timeout.
    """

    payload = {"messages": [{"role": "user", "content": user_query}]}

    try:
        result: Any = await asyncio.wait_for(agent.ainvoke(payload), timeout=45)
    except asyncio.TimeoutError:
        print(
            "Timed out waiting for the LLM. If you're using Ollama, make sure it's running and the model is pulled."
        )
        return
    except Exception as e:
        print(f"Agent error: {e}")
        return

    final_text: str | None = None

    if isinstance(result, dict):
        messages = result.get("messages")
        if messages:
            last = messages[-1]
            if isinstance(last, dict):
                final_text = last.get("content")
            else:
                final_text = getattr(last, "content", None)

    if not final_text and hasattr(result, "content"):
        final_text = getattr(result, "content", None)

    if final_text:
        print(final_text)
    else:
        print("(No assistant text returned)")


async def chat():
    """Interactive chat for curriculum planning."""

    agent = await initialize_agent()

    print("Hello! I'm the Auto Insurance Curriculum Planner Agent")
    print("Tell me your customer id and whether you want to plan or view your curriculum.")
    print("Examples:")
    print("Plan a curriculum for customer id 2")
    print("Show my curriculum for customer 2")
    print("Type 'exit' to quit.")
    print()

    while True:
        user_query = input("> ").strip()
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit"}:
            break

        await run_agent(agent, user_query)


async def run_cli(queries: list[str]):
    """Run one or more queries non-interactively."""

    agent = await initialize_agent()

    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        print(f"> {q}")
        await run_agent(agent, q)


def _extract_customer_id(text: str) -> int | None:
    match = re.search(r"\b(customer\s*(id)?\s*)?(\d+)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(3))
    except Exception:
        return None


def _is_show_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["show", "view", "get", "see"]) and "curriculum" in t


def _is_plan_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["plan", "create", "generate", "make"]) and "curriculum" in t


async def run_direct(queries: list[str]):
    """Run queries by calling MCP tools directly (no LLM required)."""

    tools = await setup_mcp_client()

    tool_map = {getattr(t, "name", None): t for t in tools}
    plan_tool = tool_map.get("plan_curriculum")
    get_tool = tool_map.get("get_curriculum")

    if not plan_tool or not get_tool:
        available = ", ".join([k for k in tool_map.keys() if k])
        print(f"MCP tools not found. Available tools: {available}")
        return

    def _print_curriculum(curriculum_payload: Any):
        """Best-effort pretty printer for the curriculum returned by MCP tools."""

        raw = curriculum_payload

        if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
            raw = raw[0].get("text")

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                print(raw)
                return

        if not raw:
            print("(No curriculum found)")
            return

        if isinstance(raw, dict):
            raw = raw.get("curriculum") or raw.get("data") or raw

        if isinstance(raw, list):
            for idx, item in enumerate(raw, start=1):
                if isinstance(item, dict):
                    title = item.get("module") or item.get("title") or str(item)
                else:
                    title = str(item)
                print(f"{idx}. {title}")
            return

        print(raw)

    def _has_curriculum(curriculum_payload: Any) -> bool:
        """Return True if the returned payload looks like it contains at least one module."""

        raw = curriculum_payload
        if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
            raw = raw[0].get("text")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return bool(raw.strip())
        if not raw:
            return False
        if isinstance(raw, dict):
            raw = raw.get("curriculum") or raw.get("data") or raw
        if isinstance(raw, list):
            return len(raw) > 0
        return True

    for q in queries:
        q = (q or "").strip()
        if not q:
            continue

        print(f"> {q}")
        customer_id = _extract_customer_id(q)
        if customer_id is None:
            print("Please include a customer id (e.g., 'customer id 2').")
            continue

        try:
            if _is_plan_request(q):
                try:
                    existing = await get_tool.ainvoke({"customer_id": customer_id})
                except Exception as e_get:
                    if "No curriculum found" in str(e_get):
                        existing = None
                    else:
                        raise

                if existing is not None and _has_curriculum(existing):
                    print(
                        f"Curriculum already exists for customer {customer_id}. Showing existing curriculum:"
                    )
                    _print_curriculum(existing)
                else:
                    res = await plan_tool.ainvoke({"customer_id": customer_id})
                    _print_curriculum(res)
            elif _is_show_request(q):
                res = await get_tool.ainvoke({"customer_id": customer_id})
                _print_curriculum(res)
            else:
                print(
                    "Direct mode supports planning or showing curriculum. Try 'Plan a curriculum for customer id 2' or 'Show my curriculum for customer 2'."
                )
        except Exception as e:
            print(f"Direct MCP call failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Insurance Curriculum Planner Agent")
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Run a single query (can be provided multiple times).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a short demo: plan and then show curriculum for customer id 2.",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Bypass the LLM and call MCP tools directly for faster responses.",
    )

    args = parser.parse_args()

    if args.demo and args.direct:
        demo_queries = [
            "Plan a curriculum for customer id 2",
            "Show my curriculum for customer 2",
        ]
        asyncio.run(run_direct(demo_queries))
    elif args.demo:
        demo_queries = [
            "Plan a curriculum for customer id 2",
            "Show my curriculum for customer 2",
        ]
        asyncio.run(run_cli(demo_queries))
    elif args.query and args.direct:
        asyncio.run(run_direct(args.query))
    elif args.query:
        asyncio.run(run_cli(args.query))
    else:
        asyncio.run(chat())
