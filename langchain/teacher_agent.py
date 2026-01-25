import asyncio
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langchain_mcp_adapters.client import MultiServerMCPClient

import insurance_mcp


def _pick_tool(tools, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    raise RuntimeError(
        f"Tool '{name}' not found. Available: {[getattr(t, 'name', '?') for t in tools]}"
    )


def _extract_int(s: str) -> int | None:
    m = re.search(r"\d+", s or "")
    return int(m.group(0)) if m else None


@dataclass(frozen=True)
class Lesson:
    title: str
    objective: str
    key_points: List[str]
    analogy: str
    worked_example_q: str
    worked_example_a: str
    checkpoint_q: str
    checkpoint_expected: str


def build_khan_style_lesson(module_title: str, module_description: str, age: int) -> Lesson:
    """Create a deterministic, Khan-Academy-style "video script" lesson.

    This is intentionally LLM-free so tests are stable.
    """

    title_l = (module_title or "").lower()
    teen = int(age) < 18

    def teenify(s: str) -> str:
        if not teen:
            return s
        return s.replace("out of pocket", "out of your own money")

    # Defaults (fallback)
    objective = f"Understand the basics of {module_title}."
    key_points = [
        f"What {module_title} means",
        "Why it matters in real life",
        "A quick example to lock it in",
    ]
    analogy = teenify(
        "Think of insurance like a safety net: it helps when something expensive happens, but there are rules."
    )
    worked_q = "In your own words, summarize the concept in one sentence."
    worked_a = teenify(module_description or f"It's an overview of {module_title} and how it affects you.")
    checkpoint_q = f"Quick check: What is the main idea of '{module_title}'?"
    checkpoint_expected = worked_a

    if "deductible" in title_l:
        objective = "Explain what a deductible is and how it changes what you pay."
        key_points = [
            "A deductible is what you pay first",
            "Insurance usually pays the rest (if covered)",
            "Higher deductibles often mean lower premiums",
        ]
        analogy = teenify(
            "It's like a game with an entry fee: you pay the entry fee first, then the game (insurance) starts helping." 
        )
        worked_q = "Your deductible is $500 and repairs cost $1,800. How much do you pay?"
        worked_a = teenify("You pay $500 out of pocket. Insurance typically covers the remaining ~$1,300.")
        checkpoint_q = "Quick check: What does 'deductible' mean?"
        checkpoint_expected = teenify(
            "The amount you pay out of pocket before your insurance starts paying for a covered claim."
        )

    elif "premium" in title_l:
        objective = "Define premium and connect it to coverage and risk."
        key_points = [
            "Premium = what you pay to keep insurance active",
            "It can be monthly/6-month/annual",
            "Price depends on risk (age, car, driving history, location)",
        ]
        analogy = "It's like a subscription: you pay to keep access turned on."
        worked_q = "If you stop paying your premium, what happens over time?"
        worked_a = "Your policy can lapse/cancel, meaning you may have no coverage."
        checkpoint_q = "Quick check: What is an insurance premium?"
        checkpoint_expected = "The amount you pay to keep your insurance coverage active."

    elif "claim" in title_l and "file" not in title_l:
        objective = "Explain what a claim is and when you should make one."
        key_points = [
            "A claim is a request for coverage/payment",
            "You file it after a covered loss",
            "Documentation helps (photos, report, details)",
        ]
        analogy = "It's like opening a help ticket with your insurance company."
        worked_q = "Is a claim the same thing as an accident?"
        worked_a = "No. The accident is the event; the claim is the request you submit for coverage/payment."
        checkpoint_q = "Quick check: What's a claim?"
        checkpoint_expected = (
            "A request you make to your insurance company to pay for a covered loss."
        )

    elif "coverage" in title_l:
        objective = "Explain what coverage means and how exclusions matter."
        key_points = [
            "Coverage is what your policy will pay for",
            "Policies have limits, conditions, and exclusions",
            "State minimums may not equal 'enough' protection",
        ]
        analogy = "Coverage is your menu: it lists what you're ordering (and what you're not)."
        worked_q = "True/False: If something is excluded, insurance still pays if you ask."
        worked_a = "False. If it's excluded/not covered, the insurer usually won't pay."
        checkpoint_q = "Quick check: What does 'coverage' mean?"
        checkpoint_expected = "What your policy will pay for (and under which conditions)."

    return Lesson(
        title=module_title,
        objective=objective,
        key_points=[teenify(p) for p in key_points],
        analogy=teenify(analogy),
        worked_example_q=teenify(worked_q),
        worked_example_a=teenify(worked_a),
        checkpoint_q=teenify(checkpoint_q),
        checkpoint_expected=teenify(checkpoint_expected),
    )


def render_lesson_script(lesson: Lesson) -> str:
    """Pretty-print the lesson like a short Khan Academy video transcript."""

    lines: List[str] = []
    lines.append(f"Lesson: {lesson.title}")
    lines.append("")
    lines.append(f"Objective: {lesson.objective}")
    lines.append("")
    lines.append("Key points:")
    for p in lesson.key_points:
        lines.append(f"- {p}")
    lines.append("")
    lines.append(f"Analogy: {lesson.analogy}")
    lines.append("")
    lines.append("Worked example:")
    lines.append(f"Q: {lesson.worked_example_q}")
    lines.append(f"A: {lesson.worked_example_a}")
    lines.append("")
    lines.append("Checkpoint:")
    lines.append(f"Q: {lesson.checkpoint_q}")
    return "\n".join(lines)


async def setup_mcp_client():
    url = os.getenv("INSURANCE_MCP_URL", "http://127.0.0.1:8000/mcp")
    client = MultiServerMCPClient(
        {
            "insurance": {
                "url": url,
                "transport": "http",
            }
        }
    )
    return await client.get_tools()


def _ensure_seed_data(db_path: str, customer_id: int):
    """Optional convenience for local demos: if customer/profile/curriculum aren't present, create them."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        customer = conn.execute("SELECT id, age FROM customers WHERE id = ?;", (customer_id,)).fetchone()

    if customer is None:
        insurance_mcp.get_customer_info(
            id=customer_id,
            name="Demo User",
            age=16,
            state="CA",
            vehicleName="Honda Accord",
            coverageType="Liability",
        )

    try:
        insurance_mcp.get_curriculum_impl(customer_id)
    except Exception:
        insurance_mcp.plan_curriculum(customer_id)


async def run_cli_local():
    """Local mode: generate a lesson script + then practice with flashcards."""

    customer_id_in = input("Customer id: ").strip()
    customer_id = _extract_int(customer_id_in)
    if customer_id is None:
        raise ValueError("Please enter a numeric customer id.")

    if os.getenv("TEACHER_SEED_DEMO", "true").strip().lower() in {"1", "true", "yes", "on"}:
        _ensure_seed_data(insurance_mcp.db_path, customer_id)

    curriculum = insurance_mcp.get_curriculum_impl(customer_id)
    print("\nCurriculum modules:")
    for m in curriculum:
        print(f"  {m.get('order')}. {m.get('module')}")

    module_in = input("\nPick a module order: ").strip()
    module_order = _extract_int(module_in)
    if module_order is None:
        raise ValueError("Please choose a module order (number).")

    module = next((m for m in curriculum if int(m.get("order")) == int(module_order)), None)
    if not module:
        raise ValueError("That module order doesn't exist for this curriculum.")

    lesson = build_khan_style_lesson(
        module_title=str(module.get("module")),
        module_description=str(module.get("description")),
        age=int(module.get("customerAge", 18)),
    )
    print("\n" + render_lesson_script(lesson))

    ans = input("\nYour checkpoint answer: ")
    score = insurance_mcp._keyword_score(ans, lesson.checkpoint_expected)
    passed = bool(score >= 0.6)
    print(f"Checkpoint result: {'pass' if passed else 'try again'} (score={score:.2f})")
    if not passed:
        print(f"Expected idea: {lesson.checkpoint_expected}")

    print("\nNow let's practice with flashcards...")
    session = insurance_mcp.start_flashcard_quiz_impl(customer_id=customer_id, module_order=module_order, limit=15)
    session_id = session["sessionId"]

    while True:
        nxt = insurance_mcp.get_next_flashcard_impl(session_id=session_id)
        if nxt.get("done"):
            print("\nAll done")
            break

        card = nxt["card"]
        print("\n---")
        print(f"Q: {card['front']}")
        try:
            a = input("Answer: ")
        except EOFError:
            break
        graded = insurance_mcp.submit_flashcard_answer_impl(session_id=session_id, card_id=card["cardId"], answer=a)
        print(f"Result: {'correct' if graded['correct'] else 'wrong'} (score={graded['score']:.2f})")
        print(f"Expected: {graded['expected']}")


async def run_cli():
    """MCP/HTTP mode: uses tools for curriculum lookup + quiz session, but keeps lesson generation local."""

    tools = await setup_mcp_client()
    get_curriculum_tool = _pick_tool(tools, "get_curriculum")
    start_tool = _pick_tool(tools, "start_flashcard_quiz")
    next_tool = _pick_tool(tools, "get_next_flashcard")
    submit_tool = _pick_tool(tools, "submit_flashcard_answer")

    customer_id_in = input("Customer id: ").strip()
    customer_id = _extract_int(customer_id_in)
    if customer_id is None:
        raise ValueError("Please enter a numeric customer id.")

    curriculum = await get_curriculum_tool.ainvoke({"customer_id": customer_id})
    if isinstance(curriculum, dict) and "curriculum" in curriculum:
        curriculum = curriculum["curriculum"]

    print("\nCurriculum modules:")
    for m in curriculum:
        print(f"  {m.get('order')}. {m.get('module')}")

    module_in = input("\nPick a module order: ").strip()
    module_order = _extract_int(module_in)
    if module_order is None:
        raise ValueError("Please choose a module order (number).")

    module = next((m for m in curriculum if int(m.get("order")) == int(module_order)), None)
    if not module:
        raise ValueError("That module order doesn't exist for this curriculum.")

    lesson = build_khan_style_lesson(
        module_title=str(module.get("module")),
        module_description=str(module.get("description")),
        age=int(module.get("customerAge", 18)),
    )
    print("\n" + render_lesson_script(lesson))

    ans = input("\nYour checkpoint answer: ")
    score = insurance_mcp._keyword_score(ans, lesson.checkpoint_expected)
    passed = bool(score >= 0.6)
    print(f"Checkpoint result: {'pass' if passed else 'try again'} (score={score:.2f})")
    if not passed:
        print(f"Expected idea: {lesson.checkpoint_expected}")

    print("\nNow let's practice with flashcards...")
    session = await start_tool.ainvoke({"customer_id": customer_id, "module_order": module_order, "limit": 15})
    session_id = session["sessionId"]

    while True:
        nxt = await next_tool.ainvoke({"session_id": session_id})
        if nxt.get("done"):
            print("\nAll done")
            break
        card = nxt["card"]
        print("\n---")
        print(f"Q: {card['front']}")
        a = input("Answer: ")
        graded = await submit_tool.ainvoke({"session_id": session_id, "card_id": card["cardId"], "answer": a})
        print(f"Result: {'correct' if graded['correct'] else 'wrong'} (score={graded['score']:.2f})")
        print(f"Expected: {graded['expected']}")


if __name__ == "__main__":
    mode = os.getenv("TEACHER_MODE", "local").strip().lower()
    if mode == "mcp":
        asyncio.run(run_cli())
    else:
        asyncio.run(run_cli_local())
