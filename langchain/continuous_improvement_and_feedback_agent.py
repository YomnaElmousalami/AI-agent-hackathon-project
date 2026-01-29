import asyncio
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

import insurance_mcp


def _sorted_counts(counts: dict) -> list[tuple[str, int]]:
	items = list(counts.items())
	items.sort(key=lambda x: (-x[1], x[0]))
	return items


async def run_cli():
	"""Continuous Improvement CLI.

	This reads telemetry from `feedback_events` and prints:
	- event counts by agent/type
	- recent events
	- simple 'where users get stuck' heuristics
	"""

	customer_id = int(input("Customer id: ").strip())
	limit_raw = input("How many recent events to analyze? (default 50): ").strip()
	limit = int(limit_raw) if limit_raw else 50

	summary = insurance_mcp.get_feedback_summary_impl(customer_id=customer_id, limit=limit)

	print("\n=== Feedback summary ===")
	print(f"Customer: {summary['customerId']}")
	print(f"Total events: {summary['totalEvents']}")

	print("\nEvent counts (agent:type):")
	for k, v in _sorted_counts(summary.get("counts", {})):
		print(f"- {k}: {v}")

	missing_counts: dict[str, int] = {}
	escalations = 0

	for ev in summary.get("recent", []):
		if ev.get("agent") == "claims_preparation" and ev.get("type") == "prepared":
			payload = ev.get("payload") or {}
			for item in payload.get("missing", []) or []:
				missing_counts[str(item)] = missing_counts.get(str(item), 0) + 1
		if ev.get("agent") == "escalation_and_routing" and ev.get("type") == "routed":
			escalations += 1

	print("\n=== Insights ===")
	if missing_counts:
		print("Most common missing items during claim prep:")
		for k, v in _sorted_counts(missing_counts)[:5]:
			print(f"- {k}: {v}")
	else:
		print("No repeated missing-fields patterns detected in this window.")

	print(f"Escalations in this window: {escalations}")
	if escalations > 0:
		print("Tip: If escalations are frequent, improve the earlier steps (reporting + evidence collection).")

	print("\nRecent events:")
	for ev in summary.get("recent", [])[:10]:
		print(f"- {ev['createdAt']} | {ev['agent']}:{ev['type']} | {ev.get('payload')}")


if __name__ == "__main__":
	asyncio.run(run_cli())

