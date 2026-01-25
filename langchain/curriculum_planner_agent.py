import asyncio
import os
import sys
from pathlib import Path
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
    """Run the agent
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


def extract_customer_id(text: str) -> int | None:
    """Extract the first integer that looks like a customer id from free-form text."""

    match = re.search(r"\b(customer\s*(id)?\s*)?(\d+)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(3))
    except Exception:
        return None


def is_show_request(text: str) -> bool:
    t = text.lower()
    return "curriculum" in t and any(k in t for k in ["show", "view", "get", "see"])


def is_plan_request(text: str) -> bool:
    t = text.lower()
    return "curriculum" in t and any(k in t for k in ["plan", "create", "generate", "make"])


def unwrap_payload(payload: Any) -> Any:
    """Best-effort normalization of MCP tool payloads for printing/logic."""

    raw = payload
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
        raw = raw[0].get("text")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return raw
    if isinstance(raw, dict):
        return raw.get("curriculum") or raw.get("data") or raw
    return raw


def has_curriculum(payload: Any) -> bool:
    raw = unwrap_payload(payload)
    if raw is None:
        return False
    if isinstance(raw, str):
        return bool(raw.strip()) and "no curriculum" not in raw.lower()
    if isinstance(raw, list):
        return len(raw) > 0
    if isinstance(raw, dict):
        return len(raw) > 0
    return True


def print_curriculum(payload: Any) -> None:
    raw = unwrap_payload(payload)
    if not raw:
        print("(No curriculum found)")
        return
    if isinstance(raw, list):
        for idx, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                title = item.get("module") or item.get("title") or str(item)
            else:
                title = str(item)
            print(f"{idx}. {title}")
        return
    print(raw)


async def handle_query(user_query: str) -> None:
    """Handle a query by preferring direct MCP tool calls; fall back to the LLM agent."""

    customer_id = extract_customer_id(user_query)

    if customer_id is not None and (is_show_request(user_query) or is_plan_request(user_query)):
        tools = await setup_mcp_client()
        tool_map = {getattr(t, "name", None): t for t in tools}
        plan_tool = tool_map.get("plan_curriculum")
        get_tool = tool_map.get("get_curriculum")

        if not plan_tool or not get_tool:
            available = ", ".join([k for k in tool_map.keys() if k])
            print(f"MCP tools not found. Available tools: {available}")
            return

        if is_show_request(user_query):
            try:
                res = await get_tool.ainvoke({"customer_id": customer_id})
                print_curriculum(res)
            except Exception as e:
                print(f"Could not fetch curriculum: {e}")
            return

        try:
            existing = None
            try:
                existing = await get_tool.ainvoke({"customer_id": customer_id})
            except Exception as e_get:
                if "no curriculum" in str(e_get).lower():
                    existing = None
                else:
                    raise

            if existing is not None and has_curriculum(existing):
                print("it already exists in the database")
                return

            res = await plan_tool.ainvoke({"customer_id": customer_id})
            _ = res
            print("done")
        except Exception as e:
            print(f"Could not plan curriculum: {e}")
        return

    agent = await initialize_agent()
    await run_agent(agent, user_query)


async def chat():
    """Interactive chat for curriculum planning."""

    print("Hello! I'm the Auto Insurance Curriculum Planner Agent")
    print("Tell me your customer id and whether you want to plan or view your curriculum.")
    print("Examples:")
    print("Plan a curriculum for customer id 2")
    print("Show the curriculum for customer 2")
    print("Type 'exit' to quit.")
    print()

    while True:
        try:
            user_query = input("> ").strip()
        except EOFError:
            break
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit"}:
            break

        await handle_query(user_query)


async def run_cli(queries: list[str]):
    """Run one or more queries non-interactively."""

    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        print(f"> {q}")
        await handle_query(q)
if __name__ == "__main__":
    asyncio.run(chat())
