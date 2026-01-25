import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from langchain_mcp_adapters.client import MultiServerMCPClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

import insurance_mcp


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
	mode = os.getenv("KNOWLEDGE_VALIDATION_MODE", "local").strip().lower()

	questions_tool = None
	start_attempt_tool = None
	record_tool = None
	if mode == "mcp":
		tools = await setup_mcp_client()
		questions_tool = _pick_tool(tools, "get_knowledge_questions")
		start_attempt_tool = _pick_tool(tools, "start_knowledge_quiz_attempt")
		record_tool = _pick_tool(tools, "record_knowledge_quiz_answer")

	customer_id = int(input("Customer id: ").strip())

	print("\nTip: You can reattempt the quiz as many times as you want.")

	def _letter(idx0: int) -> str:
		return chr(ord("A") + int(idx0))

	def _format_header(idx: int, module_order: Any, weight: float) -> str:
		if module_order is None:
			return f"Q{idx} ({weight:g} pt)"
		return f"Q{idx} (Module {module_order} | {weight:g} pt)"

	while True:
		if mode == "mcp":
			attempt = await start_attempt_tool.ainvoke(
				{"customer_id": customer_id, "questions_limit": 10}
			)
			attempt_id = attempt["attemptId"]
			qs = await questions_tool.ainvoke({"customer_id": customer_id, "limit": 10})
		else:
			attempt = insurance_mcp.start_knowledge_quiz_attempt_impl(customer_id=customer_id, questions_limit=10)
			attempt_id = attempt["attemptId"]
			qs = insurance_mcp.get_knowledge_questions_impl(customer_id=customer_id, limit=10)

		print("\nKnowledge Validation Quiz (question bank):")
		print("Scoring: multiple-choice = 1 point, true/false = 0.5 point")
		print(f"Attempt saved to DB: {attempt_id}")

		points_earned = 0.0
		points_possible = 0.0
		points_missed = 0.0
		questions_done = 0

		for idx, q in enumerate(qs, start=1):
			print("\n---")
			q_type = str(q.get("type", "multiple_choice"))
			weight = float(q.get("weight", 1.0))
			points_possible += weight
			questions_done += 1

			module_order = q.get("moduleOrder")
			print(_format_header(idx, module_order, weight))

			prompt = q.get("prompt") or q.get("scenario")
			if not prompt:
				prompt = "(question missing prompt)"
			print(prompt)

			choices = q.get("choices")
			if isinstance(choices, list) and q_type == "multiple_choice":
				for c_idx, c in enumerate(choices):
					print(f"{_letter(c_idx)}) {c}")
				print("")
				print("Answer choices: A-D (or 1-4)")
			elif q_type == "true_false":
				print("A) True")
				print("B) False")
				print("")
				print("Answer choices: A/B (or True/False)")

			ans = input("Answer: ")
			if mode == "mcp":
				result = await record_tool.ainvoke(
					{
						"customer_id": customer_id,
						"attempt_id": attempt_id,
						"question_id": q["id"],
						"answer": ans,
					}
				)
			else:
				result = insurance_mcp.record_knowledge_quiz_answer_impl(
					customer_id=customer_id,
					attempt_id=attempt_id,
					question_id=q["id"],
					answer=ans,
				)
			earned_now = float(result.get("score", 0.0))
			points_earned += earned_now
			missed_now = float(weight) - earned_now
			points_missed += missed_now

			print("")
			print(f"Marked: {'Correct' if result.get('correct') else 'Incorrect'}")
			print(f"Points: +{earned_now:g} / {weight:g}")

			correct_letter = None
			try:
				correct_idx = int(q.get("correctIndex", 0))
				correct_letter = _letter(correct_idx)
			except Exception:
				correct_letter = None
			correct_expected = result.get("expected")
			if correct_letter:
				print(f"Correct Answer: {correct_letter}")
				if correct_expected:
					print(f"({correct_expected})")
			else:
				print(f"Correct Answer: {correct_expected}")
			expl = (result.get("explanation") or "").strip()
			if expl:
				print(f"Why: {expl}")

			print(
				f"Score so far: {points_earned:g} points right, {points_missed:g} points wrong "
				f"(out of {points_possible:g} total) — {questions_done} questions done"
			)

		print("\n=== Final Score ===")
		print(
			f"Right: {points_earned:g} points | Wrong: {points_missed:g} points | "
			f"Total: {points_possible:g} points ({questions_done} questions done)"
		)

		again = input("\nReattempt quiz? (y/n): ").strip().lower()
		if again not in {"y", "yes"}:
			break


if __name__ == "__main__":
	asyncio.run(run_cli())

