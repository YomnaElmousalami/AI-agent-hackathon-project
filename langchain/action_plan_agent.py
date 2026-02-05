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
	mode = os.getenv("ACTION_PLAN_AGENT_MODE", "tool").strip().lower()
	report_id = read_prompt_or_stdin("Accident report id: ")

	if mode in {"agent", "react", "llm"}:
		prompt = (
			"You are the Action Plan Agent for an auto insurance accident assistant.\n"
			"Use generate_action_plan(report_id) to get structured next steps and timelines.\n"
			"Then reformat as a clear checklist with priorities and a short timeline.\n"
			"If severity is high, put safety/medical steps first.\n"
		)
		agent = await create_insurance_react_agent(prompt=prompt, transport="stdio")
		await run_react_agent(agent, f"Generate an action plan for accident report id {report_id}.")
		return

	# Default: deterministic tool call
	tools = await setup_mcp_client()
	tool = pick_tool(tools, "generate_action_plan")
	res = await tool.ainvoke({"report_id": report_id})
	res = coerce_tool_result(res)

	print("\nAction plan:")
	if res.get("severity"):
		print(f"Severity: {res['severity']}")
	print("Steps:")
	for s in res.get("steps", []):
		print(f"- ({s.get('priority')}) {s.get('step')}")
	print("\nTimeline:")
	for t in res.get("timelines", []):
		print(f"- {t.get('when')}: {t.get('what')}")


if __name__ == "__main__":
	asyncio.run(run_cli())

