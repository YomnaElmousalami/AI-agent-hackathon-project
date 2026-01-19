import asyncio
import os
import sys
from pathlib import Path
import argparse

# Ensure repo root is importable when executing this file directly.
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
            "4) Present results as a short ordered list (module title only), then offer help to dive deeper.\n"
        ),
    )

    return agent


async def run_agent(agent, user_query: str):
    """Run a single user query and print final assistant output."""

    final_text: str | None = None

    async for chunk in agent.astream({"messages": [{"role": "user", "content": user_query}]}):
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

    if final_text:
        print(final_text)


async def chat():
    """Interactive chat for curriculum planning."""

    agent = await initialize_agent()

    print("Hello! I'm the Auto Insurance Curriculum Planner Agent")
    print("Tell me your customer id and whether you want to plan or view your curriculum.")
    print("Examples:")
    print("- Plan a curriculum for customer id 2")
    print("- Show my curriculum for customer 2")
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

    args = parser.parse_args()

    if args.demo:
        demo_queries = [
            "Plan a curriculum for customer id 2",
            "Show my curriculum for customer 2",
        ]
        asyncio.run(run_cli(demo_queries))
    elif args.query:
        asyncio.run(run_cli(args.query))
    else:
        asyncio.run(chat())
