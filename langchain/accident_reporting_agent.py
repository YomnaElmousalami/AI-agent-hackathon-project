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
	mode = os.getenv("ACCIDENT_MODE", "local").strip().lower()
	tools = None
	start_tool = None
	update_tool = None
	finalize_tool = None
	if mode == "mcp":
		tools = await setup_mcp_client()
		start_tool = _pick_tool(tools, "start_accident_report")
		update_tool = _pick_tool(tools, "update_accident_report")
		finalize_tool = _pick_tool(tools, "finalize_accident_report")

	customer_id = int(input("Customer id: ").strip())
	if mode == "mcp":
		created = await start_tool.ainvoke({"customer_id": customer_id})
	else:
		import insurance_mcp
		created = insurance_mcp.start_accident_report_impl(customer_id=customer_id)
	report_id = created["reportId"]
	print(f"\nCreated report: {report_id}")

	location = input("Location: ").strip()
	injured = int(input("Injured count (0 if none): ").strip() or "0")
	drivable_in = input("Vehicle drivable? (y/n/blank unknown): ").strip().lower()
	vehicles_drivable = None
	if drivable_in in {"y", "yes"}:
		vehicles_drivable = True
	elif drivable_in in {"n", "no"}:
		vehicles_drivable = False
	notes = input("Notes (rear-end, side-impact, etc.): ").strip()
	evidence_raw = input("Evidence URLs (comma-separated, optional): ").strip()
	evidence_urls = [u.strip() for u in evidence_raw.split(",") if u.strip()] if evidence_raw else []

	if mode == "mcp":
		updated = await update_tool.ainvoke(
			{
				"report_id": report_id,
				"location": location or None,
				"injured_count": injured,
				"vehicles_drivable": vehicles_drivable,
				"notes": notes or None,
				"evidence_urls": evidence_urls,
			}
		)
	else:
		import insurance_mcp
		updated = insurance_mcp.update_accident_report_impl(
			report_id=report_id,
			location=location or None,
			injured_count=injured,
			vehicles_drivable=vehicles_drivable,
			notes=notes or None,
			evidence_urls=evidence_urls,
		)
	print(f"\nUpdated report status: {updated['status']}")

	if mode == "mcp":
		fin = await finalize_tool.ainvoke({"report_id": report_id})
	else:
		import insurance_mcp
		fin = insurance_mcp.finalize_accident_report_impl(report_id=report_id)
	print(f"Finalized: {fin['status']}")


if __name__ == "__main__":
	asyncio.run(run_cli())

