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


PROMPT = (
	"You are the Policy Interpretation Agent for an auto insurance assistant.\n"
	"Use the MCP tool interpret_policy(report_id) to retrieve coverage and deductible expectations.\n"
	"Then explain the result clearly in 5-10 bullet points, including assumptions/exclusions if present.\n"
)


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


def coerce_tool_result(res):
	return coerce_tool_result(res)


async def run_cli():
	mode = os.getenv("POLICY_AGENT_MODE", "tool").strip().lower()
	report_id = read_prompt_or_stdin("Accident report id: ")

	if mode in {"agent", "react", "llm"}:
		agent = await create_insurance_react_agent(prompt=PROMPT, transport="stdio")
		await run_react_agent(agent, f"Interpret the policy for accident report id {report_id}.")
		return

	tools = await setup_mcp_client()
	tool = pick_tool(tools, "interpret_policy")
	res = await tool.ainvoke({"report_id": report_id})
	res = coerce_tool_result(res)
	print("\nPolicy interpretation:")
	print(f"Coverage type: {res.get('coverageType')}")
	print(f"Summary: {res.get('summary')}")
	print(f"Estimated deductible: {res.get('estimatedDeductible')}")
	print(f"Estimated out of pocket: {res.get('estimatedOutOfPocket')}")
	if res.get("assumptions"):
		print("Assumptions:")
		for a in res["assumptions"]:
			print(f"- {a}")
	if res.get("exclusions"):
		print("Possible exclusions:")
		for e in res["exclusions"]:
			print(f"- {e}")


async def run_llm(report_id: str) -> str | None:
	agent = await create_insurance_react_agent(prompt=PROMPT, transport="stdio")
	return await run_react_agent(agent, f"Interpret the policy for accident report id {report_id}.")


if __name__ == "__main__":
	asyncio.run(run_cli())

