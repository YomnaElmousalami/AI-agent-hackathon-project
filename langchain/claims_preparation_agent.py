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


def _pick_tool(tools, name: str):
	for t in tools:
		if getattr(t, "name", None) == name:
			return t
	raise RuntimeError(f"Tool '{name}' not found")


def _coerce_tool_result(res):
	return coerce_tool_result(res)


async def run_cli():
	mode = os.getenv("CLAIMS_AGENT_MODE", "tool").strip().lower()
	report_id = read_prompt_or_stdin("Accident report id: ")

	if mode in {"agent", "react", "llm"}:
		prompt = (
			"You are the Claims Preparation Agent.\n"
			"Use prepare_claim_packet(report_id) to produce a claim-ready status.\n"
			"If missingItems exist, explain what they are and how to collect each item.\n"
			"Keep the response actionable and short.\n"
		)
		agent = await create_insurance_react_agent(prompt=prompt, transport="stdio")
		await run_react_agent(agent, f"Prepare a claim packet for accident report id {report_id}.")
		return

	# Default: deterministic tool call
	tools = await setup_mcp_client()
	tool = _pick_tool(tools, "prepare_claim_packet")
	res = await tool.ainvoke({"report_id": report_id})
	res = coerce_tool_result(res)
	print("\nClaim packet:")
	print(f"Status: {res.get('status')}")
	if res.get("missingItems"):
		print("Missing items:")
		for m in res["missingItems"]:
			print(f"- {m}")
	else:
		print("No missing items. Packet is ready.")


if __name__ == "__main__":
	asyncio.run(run_cli())

