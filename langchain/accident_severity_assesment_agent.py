import asyncio
import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))


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
	mode = os.getenv("ACCIDENT_MODE", "local").strip().lower()
	tools = None
	assess_tool = None
	import langchain.cli_utils as cli_utils
	if mode == "mcp":
		tools = await setup_mcp_client()
		assess_tool = pick_tool(tools, "assess_accident_severity")

	report_id = cli_utils.read_prompt_or_stdin("Accident report id (UUID from Accident Reporting): ")
	if mode == "mcp":
		res = await assess_tool.ainvoke({"report_id": report_id})
		res = cli_utils.coerce_tool_result(res)
	else:
		import insurance_mcp
		res = insurance_mcp.assess_accident_severity_impl(report_id=report_id)
	print("\nSeverity assessment:")
	print(f"Severity: {res['severity']} (urgency={res['urgency']})")
	print(f"Type: {res.get('accidentType')}")
	print(f"Rationale: {res['rationale']}")
	print("Recommended actions:")
	for a in res.get("recommendedActions", []):
		print(f"- {a}")


if __name__ == "__main__":
	asyncio.run(run_cli())

