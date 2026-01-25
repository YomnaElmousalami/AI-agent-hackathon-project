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


def _pick_tool(tools, name: str):
	for t in tools:
		if getattr(t, "name", None) == name:
			return t
	raise RuntimeError(f"Tool '{name}' not found")


async def run_cli():
	tools = await setup_mcp_client()
	tool = _pick_tool(tools, "escalate_and_route")

	report_id = input("Accident report id: ").strip()
	res = await tool.ainvoke({"report_id": report_id})
	print("\nRouting decision:")
	print(f"Routed to: {res.get('routedTo')}")
	print(f"Reason: {res.get('reason')}")
	print(f"Summary: {res.get('summary')}")


if __name__ == "__main__":
	asyncio.run(run_cli())

