import asyncio
import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))


from langchain.cli_utils import coerce_tool_result, read_prompt_or_stdin

from langchain.agent_runner import create_insurance_react_agent, run_react_agent


def mcp_server_path() -> str:
	return str(REPO_ROOT / "insurance_mcp.py")


async def setup_mcp_client():
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
	raise RuntimeError(f"Tool '{name}' not found")


async def run_cli():
	mode = os.getenv("ESCALATION_AGENT_MODE", "tool").strip().lower()
	report_id = read_prompt_or_stdin("Accident report id: ")

	if mode in {"agent", "react", "llm"}:
		prompt = (
			"You are the Escalation & Routing Agent.\n"
			"Use the tool escalate_and_route(report_id) to decide whether to route to a human or emergency contact.\n"
			"Return a tight summary and list any phone numbers/links provided.\n"
			"Never hallucinate phone numbers. Only output what the tool returns.\n"
		)
		agent = await create_insurance_react_agent(prompt=prompt, transport="stdio")
		await run_react_agent(agent, f"Escalate and route for accident report id {report_id}.")
		return

	# Default: deterministic tool call
	tools = await setup_mcp_client()
	tool = pick_tool(tools, "escalate_and_route")
	res = await tool.ainvoke({"report_id": report_id})
	res = coerce_tool_result(res)
	print("\nRouting decision:")
	print(f"Routed to: {res.get('routedTo')}")
	print(f"Reason: {res.get('reason')}")
	print(f"Summary: {res.get('summary')}")

	contacts = res.get("contactNumbers") or []
	if contacts:
		print("\nHelpful phone numbers:")
		for c in contacts:
			label = c.get("label") or c.get("type") or "Contact"
			phone = c.get("phone")
			url = c.get("url")
			note = c.get("note")
			bits = []
			if phone:
				bits.append(str(phone))
			if url:
				bits.append(str(url))
			line = " - ".join(bits) if bits else "(see link)"
			print(f"- {label}: {line}")
			if note:
				print(f"  Note: {note}")


if __name__ == "__main__":
	asyncio.run(run_cli())

