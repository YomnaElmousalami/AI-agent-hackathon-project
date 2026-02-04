import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from llm.llama import get_llm


REPO_ROOT = Path(__file__).resolve().parents[1]


def mcp_server_path() -> str:
	"""Absolute path to the repo's MCP server script."""
	return str(REPO_ROOT / "insurance_mcp.py")


async def setup_insurance_mcp_tools(*, transport: str = "stdio"):
	"""Return a list of MCP tools exposed by `insurance_mcp.py`.

	Defaults to `stdio` to match most CLI agents in this repo.
	Set `transport="http"` and provide `INSURANCE_MCP_URL` if you want HTTP.
	"""

	transport = (transport or "").strip().lower()
	if transport not in {"stdio", "http"}:
		raise ValueError("transport must be 'stdio' or 'http'")

	if transport == "http":
		url = os.getenv("INSURANCE_MCP_URL", "http://127.0.0.1:8000/mcp")
		client = MultiServerMCPClient(
			{
				"insurance": {
					"url": url,
					"transport": "http",
				}
			}
		)
		return await client.get_tools()

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


def pick_tool(tools, name: str):
	for t in tools:
		if getattr(t, "name", None) == name:
			return t
	raise RuntimeError(
		f"Tool '{name}' not found. Available: {[getattr(t, 'name', '?') for t in tools]}"
	)


async def create_insurance_react_agent(*, prompt: str, transport: str = "stdio"):
	"""Create a LangGraph ReAct agent wired to the Insurance MCP tools."""
	llm = get_llm()
	tools = await setup_insurance_mcp_tools(transport=transport)
	return create_react_agent(model=llm, tools=tools, prompt=prompt)


def _extract_final_assistant_text(result: Any) -> Optional[str]:
	"""Best-effort extraction of the final assistant message text."""

	if isinstance(result, dict):
		messages = result.get("messages")
		if messages:
			last = messages[-1]
			if isinstance(last, dict):
				return last.get("content")
			return getattr(last, "content", None)

	return getattr(result, "content", None)


async def run_react_agent(agent, user_query: str, *, timeout_s: int = 60) -> Optional[str]:
	"""Invoke a ReAct agent and print the final assistant message.

	Returns the final assistant text (if any).
	"""

	payload: Dict[str, Any] = {"messages": [{"role": "user", "content": user_query}]}
	try:
		result: Any = await asyncio.wait_for(agent.ainvoke(payload), timeout=timeout_s)
	except asyncio.TimeoutError:
		print(
			"Timed out waiting for the LLM. If you're using Ollama, make sure it's running and the model is pulled."
		)
		return None
	except (asyncio.CancelledError, KeyboardInterrupt):
		print("\n(LLM response cancelled.)")
		return None
	except Exception as e:
		print(f"Agent error: {e}")
		return None

	final_text = _extract_final_assistant_text(result)
	if final_text:
		print(final_text)
	return final_text


def run_chat_loop(
	*,
	agent_factory,
	greeting_lines: Iterable[str],
):
	"""Small synchronous wrapper around an async agent chat loop.

	`agent_factory` is an async callable returning an agent.
	"""

	async def _loop():
		agent = await agent_factory()
		for line in greeting_lines:
			print(line)
		print("Type 'exit' to quit.\n")

		while True:
			try:
				user_query = input("> ").strip()
			except EOFError:
				break
			if not user_query:
				continue
			if user_query.lower() in {"exit", "quit"}:
				break
			await run_react_agent(agent, user_query)

	asyncio.run(_loop())
