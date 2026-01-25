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
    except KeyboardInterrupt:
        raise
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
    """Run onboarding, then generate a curriculum plan.
    """
    await run_agent(onboarding_agent, user_query)

    import re

    match = re.search(r"\b(\d+)\b", user_query)
    if not match:
        return

    customer_id = int(match.group(1))

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
        user_query = input("> ").strip()
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit"}:
            break
        
        await onboard(agent, user_query)


if __name__ == "__main__":
    asyncio.run(chat())