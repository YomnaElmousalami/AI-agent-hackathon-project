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

from langchain.cli_utils import prompt_int, prompt_text


def pick_tool(tools, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    raise RuntimeError(
        f"Tool '{name}' not found. Available: {[getattr(t, 'name', '?') for t in tools]}"
    )


def extract_int(s: str) -> int | None:
    m = re.search(r"\d+", s or "")
    return int(m.group(0)) if m else None


@dataclass(frozen=True)
class Lesson:
    title: str
    objective: str
    hook: str
    key_points: List[str]
    analogy: str
    worked_example_q: str
    worked_example_a: str
    recap: str


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

    hook = teenify(
        "Quick story: imagine you use your car for deliveries for a week, then you get into a fender bender."
        " The big question becomes: does your insurance treat that trip differently?"
    )
    objective = (
        f"By the end, you'll be able to explain '{module_title}' in plain language and know when it matters."
    )
    key_points = [
        "Define the concept in one sentence",
        "Know the real-world situation where it shows up",
        "Spot a common mistake teens make around it",
    ]
    analogy = teenify(
        "Think of insurance like the rules of a sport: the game is the same, but the rules change depending on how you're playing."
    )
    worked_q = teenify(
        "Scenario: You're driving your own car to school, then later you start using the same car to deliver food on weekends. "
        "What's the key insurance difference?"
    )
    worked_a = teenify(
        "Personal auto usually covers normal personal driving (school, errands). If you use the car to make money (deliveries/rideshare), "
        "you may need commercial coverage or a specific endorsement—otherwise a claim could be denied."
    )
    recap = teenify(
        "Recap: personal = everyday driving. commercial = business driving. The 'why' is risk: business driving changes how much and why you drive."
    )

    if "deductible" in title_l:
        hook = teenify(
            "Here's the most common surprise: you can have insurance and STILL pay money after a crash. That first chunk is the deductible."
        )
        objective = "Explain what a deductible is and how it changes what you pay in a claim."
        key_points = [
            "Deductible = what you pay first when you file a covered claim",
            "It applies per claim (not usually per month)",
            "Higher deductible often means a cheaper premium (tradeoff)",
        ]
        analogy = teenify(
            "It's like a video game: you have to clear the first level (deductible) before you unlock the power-up (insurance paying)." 
        )
        worked_q = "Your deductible is $500 and repairs cost $1,800. How much do you pay?"
        worked_a = teenify("You pay $500 out of pocket. Insurance typically covers the remaining ~$1,300.")
        recap = teenify(
            "Recap: deductible is the 'you pay first' amount. Picking a higher one can lower your premium, but it makes accidents more expensive upfront."
        )

    elif "premium" in title_l:
        hook = "Every insurance bill is basically a membership fee to keep your protection turned on. That's the premium."
        objective = "Define premium and connect it to coverage and risk (why your price changes)."
        key_points = [
            "Premium = what you pay to keep insurance active",
            "It can be monthly/6-month/annual",
            "Price depends on risk (age, car, driving history, location)",
        ]
        analogy = "It's like a subscription: you pay to keep access turned on."
        worked_q = "If you stop paying your premium, what happens over time?"
        worked_a = "Your policy can lapse/cancel, meaning you may have no coverage."
        recap = "Recap: premium keeps coverage active. More risk or more coverage usually means a higher premium."

    elif "claim" in title_l and "file" not in title_l:
        hook = "A claim is the moment you ask your insurance to step in and help pay."
        objective = "Explain what a claim is, when to file one, and what info makes it go smoothly."
        key_points = [
            "A claim is a request for coverage/payment",
            "You file it after a covered loss",
            "Documentation helps (photos, report, details)",
        ]
        analogy = "It's like opening a support ticket: you describe the issue and provide proof so it can be resolved."
        worked_q = "Accident vs claim: what's the difference?"
        worked_a = "The accident is the event. The claim is the request you submit to your insurer to pay for a covered loss."
        recap = "Recap: accident happened; claim is what you file. Photos + details make claims faster."

    elif "coverage" in title_l:
        hook = "Coverage answers the question: 'What exactly will my insurance pay for?'"
        objective = "Explain what coverage means, plus limits and exclusions (the fine print that matters)."
        key_points = [
            "Coverage is what your policy will pay for",
            "Policies have limits, conditions, and exclusions",
            "State minimums may not equal 'enough' protection",
        ]
        analogy = "Coverage is your menu: it lists what you're ordering (and what you're not)."
        worked_q = "True/False: If something is excluded, insurance still pays if you ask."
        worked_a = "False. If it's excluded/not covered, the insurer usually won't pay."
        recap = "Recap: coverage = what gets paid. Limits cap the payment. Exclusions mean 'not covered'."

    return Lesson(
        title=module_title,
        objective=objective,
        hook=teenify(hook),
        key_points=[teenify(p) for p in key_points],
        analogy=teenify(analogy),
        worked_example_q=teenify(worked_q),
        worked_example_a=teenify(worked_a),
        recap=teenify(recap),
    )


def render_lesson_script(lesson: Lesson) -> str:
    """Pretty-print the lesson like a short Khan Academy video transcript.

    We don't stream real videos in this repo. Instead, we output a "video-like" experience:
    a small playlist plus a timestamped transcript.
    """

    lines: List[str] = []

    lines.append("Video playlist (Khan style):")
    lines.append(f"1) {lesson.title} — 6:00")
    lines.append(f"2) {lesson.title}: Real-life Scenario Walkthrough — 3:00")
    lines.append(f"3) {lesson.title}: Summary & Common Mistakes — 1:30")
    lines.append("")

    lines.append(f"Lesson: {lesson.title}")
    lines.append("")
    lines.append(f"[00:00] Hook: {lesson.hook}")
    lines.append("")
    lines.append(f"[00:20] Objective: {lesson.objective}")
    lines.append("")
    lines.append("[00:45] Key points:")
    for p in lesson.key_points:
        lines.append(f"- {p}")
    lines.append("")
    lines.append(f"[02:00] Analogy: {lesson.analogy}")
    lines.append("")
    lines.append("[03:00] Worked example:")
    lines.append("(Scenario walkthrough)")
    lines.append(f"Q: {lesson.worked_example_q}")
    lines.append(f"A: {lesson.worked_example_a}")
    lines.append("")
    lines.append(f"[05:30] Recap: {lesson.recap}")

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


def ensure_seed_data(db_path: str, customer_id: int):
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
    """Local mode: choose a module and watch a "Khan-style" lesson, then practice."""

    customer_id = prompt_int("Customer id: ", min_value=1)

    if os.getenv("TEACHER_SEED_DEMO", "true").strip().lower() in {"1", "true", "yes", "on"}:
        ensure_seed_data(insurance_mcp.db_path, customer_id)

    curriculum = insurance_mcp.get_curriculum_impl(customer_id)
    print("\nCurriculum modules:")
    for m in curriculum:
        print(f"  {m.get('order')}. {m.get('module')}")

    module_order = prompt_int("\nPick a module order: ", min_value=1)

    module = next((m for m in curriculum if int(m.get("order")) == int(module_order)), None)
    if not module:
        raise ValueError("That module order doesn't exist for this curriculum.")

    try:
        insurance_mcp.record_teacher_module_view_impl(
            customer_id=int(customer_id),
            module_order=int(module_order),
            module_title=str(module.get("module")),
        )
    except Exception:
        pass

    lesson = build_khan_style_lesson(
        module_title=str(module.get("module")),
        module_description=str(module.get("description")),
        age=int(module.get("customerAge", 18)),
    )
    print("\nNow playing (simulated):")
    print(render_lesson_script(lesson))

    print("\nLesson complete.")


async def run_cli():
    """MCP/HTTP mode: uses tools for curriculum lookup + quiz session, but keeps lesson generation local."""

    tools = await setup_mcp_client()
    get_curriculum_tool = pick_tool(tools, "get_curriculum")

    customer_id = prompt_int("Customer id: ", min_value=1)

    curriculum = await get_curriculum_tool.ainvoke({"customer_id": customer_id})
    if isinstance(curriculum, dict) and "curriculum" in curriculum:
        curriculum = curriculum["curriculum"]

    print("\nCurriculum modules:")
    for m in curriculum:
        print(f"  {m.get('order')}. {m.get('module')}")

    module_order = prompt_int("\nPick a module order: ", min_value=1)

    module = next((m for m in curriculum if int(m.get("order")) == int(module_order)), None)
    if not module:
        raise ValueError("That module order doesn't exist for this curriculum.")

    try:
        insurance_mcp.record_teacher_module_view_impl(
            customer_id=int(customer_id),
            module_order=int(module_order),
            module_title=str(module.get("module")),
        )
    except Exception:
        pass

    lesson = build_khan_style_lesson(
        module_title=str(module.get("module")),
        module_description=str(module.get("description")),
        age=int(module.get("customerAge", 18)),
    )
    print("\n" + render_lesson_script(lesson))

    print("\nLesson complete.")


if __name__ == "__main__":
    mode = os.getenv("TEACHER_MODE", "local").strip().lower()
    if mode == "mcp":
        asyncio.run(run_cli())
    else:
        asyncio.run(run_cli_local())
