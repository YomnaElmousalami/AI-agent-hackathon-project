import asyncio
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

import insurance_mcp

from langchain.cli_utils import prompt_int


def _sorted_counts(counts: dict) -> list[tuple[str, int]]:
	items = list(counts.items())
	items.sort(key=lambda x: (-x[1], x[0]))
	return items


def _key(payload: dict | None, *path: str) -> str | None:
	"""Safe nested lookup helper for telemetry payloads."""
	cur: object = payload or {}
	for p in path:
		if not isinstance(cur, dict):
			return None
		cur = cur.get(p)
	return cur if isinstance(cur, str) else None


def _bool(payload: dict | None, *path: str) -> bool | None:
	cur: object = payload or {}
	for p in path:
		if not isinstance(cur, dict):
			return None
		cur = cur.get(p)
	if isinstance(cur, bool):
		return cur
	return None


def _top_n(counts: dict[str, int], n: int = 5) -> list[tuple[str, int]]:
	return _sorted_counts(counts)[:n]


async def run_cli():
	"""Continuous Improvement CLI.

	This reads telemetry from `feedback_events` and prints:
	- event counts by agent/type
	- recent events
	- simple 'where users get stuck' heuristics
	"""

	customer_id = prompt_int("Customer id: ", min_value=1)
	limit = prompt_int("How many recent events to analyze? (default 50): ", min_value=1, default=50)

	summary = insurance_mcp.get_feedback_summary_impl(customer_id=customer_id, limit=limit)

	print("\n=== Feedback summary ===")
	print(f"Customer: {summary['customerId']}")
	print(f"Total events: {summary['totalEvents']}")

	print("\nEvent counts (agent:type):")
	for k, v in _sorted_counts(summary.get("counts", {})):
		print(f"- {k}: {v}")

	missing_counts: dict[str, int] = {}
	escalations = 0

	quiz_incorrect_by_qid: dict[str, int] = {}
	quiz_incorrect_by_topic: dict[str, int] = {}
	location_retry_count = 0
	accident_updates = 0

	for ev in summary.get("recent", []):
		agent = ev.get("agent")
		type_ = ev.get("type")
		payload = ev.get("payload") or {}

		if agent == "claims_preparation" and type_ == "prepared":
			for item in payload.get("missing", []) or []:
				missing_counts[str(item)] = missing_counts.get(str(item), 0) + 1

		if agent == "escalation_and_routing" and type_ == "routed":
			escalations += 1

		if agent == "knowledge_validation" and type_ == "graded":
			correct = bool(payload.get("correct"))
			qid = str(payload.get("questionId") or "").strip()
			topic = str(payload.get("topic") or "").strip()
			if not correct:
				if qid:
					quiz_incorrect_by_qid[qid] = quiz_incorrect_by_qid.get(qid, 0) + 1
				if topic:
					quiz_incorrect_by_topic[topic] = quiz_incorrect_by_topic.get(topic, 0) + 1

		if agent == "accident_reporting" and type_ == "updated":
			accident_updates += 1
			loc = str(payload.get("location") or "").strip()
			if loc and "," not in loc:
				location_retry_count += 1

	print("\n=== Insights ===")
	print("\n--- Knowledge Validation ---")

	if missing_counts:
		print("Most common missing items during claim prep:")
		for k, v in _top_n(missing_counts, 5):
			print(f"- {k}: {v}")
	else:
		print("No repeated missing-fields patterns detected in this window.")

	if quiz_incorrect_by_topic:
		print("\nMost common knowledge gaps (by topic):")
		for k, v in _top_n(quiz_incorrect_by_topic, 5):
			print(f"- {k}: {v}")
	elif quiz_incorrect_by_qid:
		print("\nMost repeated incorrect knowledge questions (by id):")
		for k, v in _top_n(quiz_incorrect_by_qid, 5):
			print(f"- {k}: {v}")
	else:
		print("\nNo repeated knowledge-validation gaps detected in this window.")

	print("\nRecommendation (Knowledge Validation):")
	if quiz_incorrect_by_topic:
		print("- Re-teach the top topic(s) above in Teacher Agent, then re-quiz the same module.")
		print("- Add 1–2 extra scenario questions for that topic to reinforce the idea.")
	else:
		print("- Keep rotating modules; no obvious repeated gaps in this window.")

	print("\n--- Accident Mode ---")
	print(f"Accident report updates in this window: {accident_updates}")
	if location_retry_count > 0:
		print(
			"Location format issues detected. Consider improving the prompt/validation and adding examples (City, ST)."
		)

	print(f"Escalations in this window: {escalations}")
	if escalations > 0:
		print("Recommendation: reduce escalations by improving earlier steps:")
		print("- Make accident reporting prompts more structured (injuries, drivable, evidence).")
		print("- Add clearer claim-prep checklists (photos, police report, vehicle/driver info).")
		print("- If routing is to 911 often, add an emergency pre-check at the very start.")
	else:
		print("Recommendation (Accident Mode):")
		print("- No escalations detected in this window — keep monitoring for spikes during real incidents.")

	print("\nRecent events:")
	for ev in summary.get("recent", [])[:10]:
		print(f"- {ev['createdAt']} | {ev['agent']}:{ev['type']} | {ev.get('payload')}")


if __name__ == "__main__":
	asyncio.run(run_cli())

