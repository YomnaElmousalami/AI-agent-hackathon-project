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

from langchain.cli_utils import prompt_int, prompt_text, prompt_yes_no_optional


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
	mode = os.getenv("KNOWLEDGE_VALIDATION_MODE", "local").strip().lower()

	questions_tool = None
	start_attempt_tool = None
	record_tool = None
	if mode == "mcp":
		tools = await setup_mcp_client()
		questions_tool = pick_tool(tools, "get_knowledge_questions")
		start_attempt_tool = pick_tool(tools, "start_knowledge_quiz_attempt")
		record_tool = pick_tool(tools, "record_knowledge_quiz_answer")

	customer_id = prompt_int("Customer id: ", min_value=1)

	default_module_order = None
	try:
		last = insurance_mcp.get_last_teacher_module_impl(customer_id=customer_id)
		if isinstance(last, dict) and last.get("moduleOrder") is not None:
			default_module_order = int(last.get("moduleOrder"))
	except Exception:
		default_module_order = None

	if default_module_order is not None:
		print(f"Detected last taught module: {default_module_order}")

	module_order = prompt_int(
		"Which module do you want to be quizzed on? (enter module order number): ",
		min_value=1,
		default=default_module_order if default_module_order is not None else 1,
	)

	try:
		insurance_mcp.record_knowledge_validation_module_view_impl(
			customer_id=int(customer_id),
			module_order=int(module_order),
		)
	except Exception:
		pass

	print("\nTip: You can reattempt the quiz as many times as you want.")

	def letter(idx0: int) -> str:
		return chr(ord("A") + int(idx0))

	def format_header(idx: int, module_order: Any, weight: float) -> str:
		if module_order is None:
			return f"Q{idx} ({weight:g} pt)"
		return f"Q{idx} (Module {module_order} | {weight:g} pt)"

	while True:
		if mode == "mcp":
			attempt = await start_attempt_tool.ainvoke(
				{"customer_id": customer_id, "questions_limit": 10, "module_order": module_order}
			)
			attempt_id = attempt["attemptId"]
			qs = await questions_tool.ainvoke(
				{"customer_id": customer_id, "limit": 10, "module_order": module_order}
			)
		else:
			attempt = insurance_mcp.start_knowledge_quiz_attempt_impl(
				customer_id=customer_id, questions_limit=10, module_order=module_order
			)
			attempt_id = attempt["attemptId"]
			qs = insurance_mcp.get_knowledge_questions_impl(
				customer_id=customer_id, limit=10, module_order=module_order
			)

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
			print(format_header(idx, module_order, weight))

			prompt = q.get("prompt") or q.get("scenario")
			if not prompt:
				prompt = "(question missing prompt)"
			print(prompt)

			choices = q.get("choices")
			if isinstance(choices, list) and q_type == "multiple_choice":
				for c_idx, c in enumerate(choices):
					print(f"{letter(c_idx)}) {c}")
				print("")
				print("Answer choices: A-D (or 1-4)")
			elif q_type == "true_false":
				print("A) True")
				print("B) False")
				print("")
				print("Answer choices: A/B (or True/False)")

			ans = prompt_text("Answer: ", allow_empty=False)
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
				correct_letter = letter(correct_idx)
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

		again = prompt_yes_no_optional("\nReattempt same module quiz? (y/n): ")
		if again is True:
			continue

		change = prompt_yes_no_optional(
			"Do you want to take a quiz for a different module? (y/n): "
		)
		if change is not True:
			break

		module_order = prompt_int(
			"Which module do you want to be quizzed on next? (enter module order number): ",
			min_value=1,
			default=module_order,
		)
		try:
			insurance_mcp.record_knowledge_validation_module_view_impl(
				customer_id=int(customer_id),
				module_order=int(module_order),
			)
		except Exception:
			pass
		continue


if __name__ == "__main__":
	asyncio.run(run_cli())

