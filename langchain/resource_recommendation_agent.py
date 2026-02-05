import asyncio
import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

import insurance_mcp

from langchain.cli_utils import prompt_int, prompt_int_optional, prompt_text


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
	"""Interactive CLI.

	Behavior:
	- Finds the user's state from the stored customer profile.
	- Accepts a resource topic.
	- Prints state-aware resources.
	- Lets the user request a short 'video-style' summary for any item.
	  Otherwise, prints one paragraph summarizing all resources.
	"""

	mode = os.getenv("RESOURCE_RECOMMENDATION_MODE", "local").strip().lower()

	tools = None
	rec_tool = None
	if mode == "mcp":
		tools = await setup_mcp_client()
		rec_tool = pick_tool(tools, "recommend_resources")

	customer_id = prompt_int("Customer id: ", min_value=1)
	topic = prompt_text("Topic you want resources for (deductible/claim/coverage/...): ", allow_empty=False)

	if mode == "mcp":
		resources = await rec_tool.ainvoke(
			{"customer_id": customer_id, "topic": topic, "limit": 8}
		)
	else:
		resources = insurance_mcp.recommend_resources_impl(
			customer_id=customer_id,
			topic=topic,
			limit=8,
		)

	state_guess = None
	for r in resources:
		t = (r.get("title") or "").strip()
		if " insurance department" in t.lower() and len(t) >= 2:
			state_guess = t.split(" ", 1)[0].upper()
			break
	if state_guess:
		print(f"\nDetected state: {state_guess}")

	print("\nRecommended resources:")
	for i, r in enumerate(resources, start=1):
		print(
			f"{i}) [{r.get('type')}] {r.get('title')}\n"
			f"   - {r.get('summary')}\n"
			f"   - {r.get('url')}"
		)

	idx = prompt_int_optional(
		"\nDo you want a video summary of any specific resource? "
		"Enter a number (e.g., 2), or press Enter for a general summary: ",
		min_value=1,
		max_value=len(resources) if resources else 1,
	)

	if idx is not None:
		picked = resources[idx - 1]
		summary = insurance_mcp.summarize_resources_impl([picked], style="video")
		print("\nVideo-style summary:")
		print(summary["summary"])
		return

	summary = insurance_mcp.summarize_resources_impl(resources, style="general")
	print("\nGeneral summary:")
	print(summary["summary"])


if __name__ == "__main__":
	asyncio.run(run_cli())

