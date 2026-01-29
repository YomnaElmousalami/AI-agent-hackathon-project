#imports
from fastmcp import FastMCP
from typing import List, Dict
from datetime import datetime, timezone
import sqlite3
import json
import uuid
import re

from database.insurance_db import init_db
import os

db_path = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))
mcp = FastMCP("AutoInsuranceMCP")
init_db(db_path)


def _connect(database_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection to the configured DB (or an override).

    Tests use `database_path` to isolate state in a tmp db.
    """

    path = database_path or db_path
    init_db(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _now_date() -> str:
    """UTC date string used across the persistence layer."""

    return datetime.now(timezone.utc).strftime("%m/%d/%Y")


def create_customer_impl(
    *,
    customer_id: int,
    name: str,
    age: int = 16,
    state: str = "VA",
    vehicle_name: str = "Unknown Vehicle",
    coverage_type: str = "liability",
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    database_path: str | None = None,
) -> Dict:
    """Create a bare customer row (for tests / non-onboarding flows).

    Note: The onboarding UI uses `get_customer_info()` which writes richer fields.
    Some tests expect a lightweight customer seeding helper.
    """

    now = _now_date()
    with _connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              age=excluded.age,
              state=excluded.state,
              vehicle_name=excluded.vehicle_name,
              coverage_type=excluded.coverage_type,
              updated_at=excluded.updated_at;
            """,
            (
                int(customer_id),
                str(name),
                int(age),
                str(state).upper(),
                str(vehicle_name),
                str(coverage_type),
                now,
                now,
            ),
        )

    return {
        "id": int(customer_id),
        "name": str(name),
        "age": int(age),
        "state": str(state).upper(),
        "vehicleName": str(vehicle_name),
        "coverageType": str(coverage_type),
        "createdAt": now,
        "updatedAt": now,
    }


def create_curriculum_plan_impl(
    *,
    customer_id: int,
    topic: str,
    difficulty: str,
    goal: str,
    database_path: str | None = None,
) -> Dict:
    """Ensure a curriculum plan exists for a customer.

    Some agent/tests want a deterministic persisted plan record before generating
    question banks / quiz attempts.
    """

    now = _now_date()

    with _connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT age FROM customers WHERE id = ?;", (int(customer_id),)).fetchone()
        customer_age = int(row["age"]) if row and row["age"] is not None else 16

        conn.execute(
            """
            INSERT INTO curriculum_plans (customer_id, customer_age, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
              customer_age=excluded.customer_age,
              updated_at=excluded.updated_at;
            """,
            (int(customer_id), int(customer_age), now, now),
        )

        plan_row = conn.execute(
            "SELECT id FROM curriculum_plans WHERE customer_id = ?;",
            (int(customer_id),),
        ).fetchone()
        plan_id = int(plan_row["id"]) if plan_row else None

        conn.execute("DELETE FROM curriculum_modules WHERE plan_id = ?;", (int(plan_id),))
        conn.execute(
            """
            INSERT INTO curriculum_modules (plan_id, module_order, module_title, module_description, created_at)
            VALUES (?, 1, ?, ?, ?)
            ON CONFLICT(plan_id, module_order) DO UPDATE SET
              module_title=excluded.module_title,
              module_description=excluded.module_description;
            """,
            (
                int(plan_id),
                str(topic),
                f"{topic} ({difficulty}) — goal: {goal}.",
                now,
            ),
        )

    return {
        "planId": plan_id,
        "customerId": int(customer_id),
        "topic": str(topic),
        "difficulty": str(difficulty),
        "goal": str(goal),
        "customerAge": int(customer_age),
        "createdAt": now,
        "updatedAt": now,
    }


def _row_to_dict(row: sqlite3.Row | None) -> Dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}

#Code here is for Learning & Education Mode:
#for user onboarding agent
@mcp.tool()
def get_customer_info(id: int, name: str, age: int, state: str, vehicleName: str, coverageType: str) -> Dict:
    """
    Retrieves customer information by ID, age, state, vehicle name, and coverage type.
    
    Args:
        id: The unique customer identifier,
        name: The name of the customer,
        age: The age of the customer,
        state: The state where the customer resides,
        vehicleName: The name of the customer's vehicle,
        coverageType: The type of insurance coverage the customer has.
    
    Returns:
        Dictionary containing customer details
    """
    
    now = datetime.now(timezone.utc).strftime("%m/%d/%Y")

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        name=excluded.name,
        age=excluded.age,
        state=excluded.state,
        vehicle_name=excluded.vehicle_name,
        coverage_type=excluded.coverage_type,
        updated_at=excluded.updated_at;
        """, (id, name, age, state, vehicleName, coverageType, now, now))
        
    return {
        "id": id,
        "name": name,
        "age": age,
        "state": state,
        "vehicleName": vehicleName,
        "coverageType": coverageType,
        "updatedAt": now
    }


# For Curriculum Planner Agent
@mcp.tool()
def plan_curriculum(customer_id: int) -> List[Dict]:
    """
    Plans a curriculum based on user age.
    
    Args:
        customer_id: The customer's ID 

    Returns:
        List of curriculum items tailored to the users age 
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, age, state, vehicle_name, coverage_type FROM customers WHERE id = ?;",
            (customer_id,),
        ).fetchone()

    #may remove later
    if row is None:
        raise ValueError(
            f"Customer {customer_id} not found. Call get_customer_info first to store the profile."
        )

    user_age = int(row["age"])

    curriculum = [
        "What is Insurance?",
        "Understanding Deductibles",
        "Steps to Take During a car accident",
        "Do's and Don'ts of Safe Driving",
        "What is a premium?",
        "What is a claim?",
        "How to file a claim?",
        "What is coverage?",
        "Types of coverage for auto insurance",
        "Factors affecting insurance rates",
        "Common auto insurance terms explained",
        "How to choose the right insurance plan",
        "Importance of liability coverage",
        "Understanding comprehensive and collision coverage",
        "How to lower your insurance premiums",
        "Seasonal driving tips and insurance implications",
        "Impact of traffic violations on insurance rates",
        "How to read your insurance policy",
        "Benefits of bundling insurance policies",
        "Understanding no-fault insurance",
        "What to do in case of a total loss",
        "How to handle uninsured motorist situations",
        "The importance of regular vehicle maintenance for insurance purposes",
        "How to update your insurance policy",
        "Understanding policy endorsements",
        "The claims process: Step-by-step guide",
        "How to dispute a denied claim",
        "The role of an insurance adjuster",
        "Understanding rental car coverage",
        "How to switch insurance providers",
        "The impact of life changes on your insurance needs",
        "Understanding roadside assistance coverage",
        "The importance of accurate vehicle information",
        "How to avoid insurance fraud",
        "Understanding gap insurance",
        "The role of telematics in auto insurance",
        "Understanding the difference between actual cash value and replacement cost",
        "How to handle multiple vehicles on one policy",
        "The impact of driving history on insurance rates",
        "Understanding the grace period for premium payments",
        "How to get discounts on auto insurance",
        "The importance of reviewing your insurance policy annually",
        "Understanding the difference between state minimums and recommended coverage",
        "How to handle insurance after a move",
        "The role of family members in an insurance policy",
        "Understanding the impact of vehicle modifications on insurance",
        "How to choose a deductible amount",
        "The importance of documenting your vehicle's condition",
        "Understanding the difference between personal and commercial auto insurance",
    ]

    if user_age < 18:
        curriculum.insert(10, "Tips for first-time drivers")
        curriculum.insert(11, "How insurance works for young drivers")
        curriculum.insert(12, "Understanding the impact of driving history on insurance rates")
        curriculum.insert(13, "The importance of safe driving courses")
        curriculum.insert(14, "How to maintain a clean driving record")
        curriculum.insert(15, "Understanding insurance requirements for student drivers")
    else:
        curriculum.insert(10, "The role of credit scores in insurance")
        
    curriculum_plan = [
        {
            "module": topic,
            "description": f"A comprehensive overview of {topic.lower()}.",
            "customerAge": user_age,
        }
        for topic in curriculum
    ]

    now = datetime.now(timezone.utc).strftime("%m/%d/%Y")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        conn.execute(
            """
            INSERT INTO curriculum_plans (customer_id, customer_age, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
              customer_age=excluded.customer_age,
              updated_at=excluded.updated_at;
            """,
            (customer_id, user_age, now, now),
        )

        plan_row = conn.execute(
            "SELECT id FROM curriculum_plans WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()
        plan_id = int(plan_row["id"])

        conn.execute("DELETE FROM curriculum_modules WHERE plan_id = ?;", (plan_id,))
        conn.executemany(
            """
            INSERT INTO curriculum_modules (plan_id, module_order, module_title, module_description, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            [
                (plan_id, idx, item["module"], item["description"], now)
                for idx, item in enumerate(curriculum_plan, start=1)
            ],
        )

    return curriculum_plan

#for teacher agent, to be determined
@mcp.tool()
def get_curriculum(customer_id: int) -> List[Dict]:
    return get_curriculum_impl(customer_id=customer_id)


def get_curriculum_impl(customer_id: int) -> List[Dict]:
    """Fetch the latest stored curriculum plan for a given customer.

    Args:
        customer_id: The customer's ID.

    Returns:
        List of persisted curriculum modules (ordered).
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        plan = conn.execute(
            "SELECT id, customer_age FROM curriculum_plans WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()

        if plan is None:
            raise ValueError(
                f"No curriculum found for customer {customer_id}. Call plan_curriculum first."
            )

        modules = conn.execute(
            """
            SELECT module_order, module_title, module_description
            FROM curriculum_modules
            WHERE plan_id = ?
            ORDER BY module_order ASC;
            """,
            (int(plan["id"]),),
        ).fetchall()

    return [
        {
            "module": m["module_title"],
            "description": m["module_description"],
            "customerAge": int(plan["customer_age"]),
            "order": int(m["module_order"]),
        }
        for m in modules
    ]


def _now_date() -> str:
    return datetime.now(timezone.utc).strftime("%m/%d/%Y")


def _normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _keyword_score(answer: str, expected: str) -> float:
    """Very small, deterministic grader.

    Returns a score in [0, 1].
    """

    a = _normalize_text(answer)
    e = _normalize_text(expected)
    if not a or not e:
        return 0.0

    if a == e:
        return 1.0

    a_set = set(a.split())
    e_set = set(e.split())
    if not a_set or not e_set:
        return 0.0

    overlap = len(a_set & e_set)
    return overlap / max(1, len(e_set))


def _age_tone(age: int) -> str:
    return "teen" if int(age) < 18 else "adult"


def _build_cards_for_module(module_title: str, module_description: str, age: int, module_order: int) -> List[Dict]:
    """Deterministic, template-based flashcards.

    This avoids requiring an LLM, but still returns useful Quizlet-style cards.
    """

    tone = _age_tone(age)
    title_l = (module_title or "").strip().lower()

    def teenify(text: str) -> str:
        if tone != "teen":
            return text
        return text.replace("out of pocket", "out of your own money")

    cards: List[Dict] = []

    def add(front: str, back: str, tags: List[str], difficulty: str = "easy"):
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "moduleOrder": int(module_order),
                "moduleTitle": module_title,
                "front": front.strip(),
                "back": teenify(back.strip()),
                "difficulty": difficulty,
                "tags": tags,
            }
        )

    add(
        front=f"In 1–2 sentences, what is this module about: '{module_title}'?",
        back=module_description or f"Overview of {module_title}.",
        tags=["overview"],
        difficulty="easy",
    )

    if "deductible" in title_l:
        add(
            "What does 'deductible' mean in auto insurance?",
            "A deductible is the amount you pay out of pocket before your insurance starts paying for a covered claim.",
            tags=["deductible", "definition"],
            difficulty="easy",
        )
        add(
            "Your deductible is $500 and repairs cost $1,800. About how much do you pay (assuming it's covered)?",
            "You pay $500 (your deductible). Insurance typically covers the remaining ~$1,300.",
            tags=["deductible", "scenario"],
            difficulty="medium",
        )

    if "premium" in title_l:
        add(
            "What is an insurance premium?",
            "A premium is the amount you pay (monthly/6-month/annual) to keep your insurance coverage active.",
            tags=["premium", "definition"],
        )

    if "claim" in title_l and "file" not in title_l:
        add(
            "What is a claim?",
            "A claim is a request you make to your insurance company to pay for a covered loss (like accident damage).",
            tags=["claim", "definition"],
        )

    if "file a claim" in title_l or "how to file" in title_l:
        add(
            "Put these in a good order: (A) Document evidence, (B) Report to insurer, (C) Ensure safety",
            "A good order is: (C) Ensure safety, (A) Document evidence, (B) Report to insurer.",
            tags=["claim", "process"],
            difficulty="medium",
        )

    if "coverage" in title_l:
        add(
            "What does 'coverage' mean in insurance?",
            "Coverage is what your policy will pay for (and under which conditions).",
            tags=["coverage", "definition"],
        )
        add(
            "True/False: If something is 'not covered', your insurer still pays if you ask nicely.",
            "False. If it's not covered by the policy (or excluded), the insurer usually won't pay.",
            tags=["coverage", "policy"],
        )

    if "accident" in title_l:
        add(
            "Name 3 things to do right after a crash.",
            "Prioritize safety (check injuries), move to a safe spot if possible, and document the scene (photos, info).",
            tags=["accident", "safety"],
            difficulty="easy",
        )

    add(
        front=f"What's one common mistake people make related to: '{module_title}'?",
        back="Common mistakes include skipping documentation, misunderstanding deductibles/coverage, or delaying reporting. (Answer can vary.)",
        tags=["reflection"],
        difficulty="hard",
    )

    return cards


@mcp.tool()
def generate_flashcards(customer_id: int, module_order: int | None = None, limit: int = 30) -> List[Dict]:
    return generate_flashcards_impl(customer_id=customer_id, module_order=module_order, limit=limit)


def generate_flashcards_impl(customer_id: int, module_order: int | None = None, limit: int = 30) -> List[Dict]:
    """Generate Quizlet-style flashcards from the saved curriculum.

    Args:
        customer_id: The customer's ID.
        module_order: Optional module order to generate cards for a single module.
        limit: Max number of cards to return.

    Returns:
        A list of flashcard dicts: {id, moduleOrder, moduleTitle, front, back, difficulty, tags}
    """

    curriculum = get_curriculum_impl(customer_id)
    cards: List[Dict] = []

    for m in curriculum:
        if module_order is not None and int(m["order"]) != int(module_order):
            continue
        cards.extend(
            _build_cards_for_module(
                module_title=m["module"],
                module_description=m.get("description", ""),
                age=int(m.get("customerAge", 18)),
                module_order=int(m["order"]),
            )
        )
        if len(cards) >= int(limit):
            break

    return cards[: int(limit)]


def _persist_quiz_session(session_id: str, customer_id: int, module_order: int | None):
    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            INSERT INTO quiz_sessions (id, customer_id, module_order, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, 'active');
            """,
            (session_id, int(customer_id), int(module_order) if module_order is not None else None, now, now),
        )


def _persist_quiz_cards(session_id: str, cards: List[Dict]):
    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executemany(
            """
            INSERT INTO quiz_cards (id, session_id, module_order, module_title, front, back, difficulty, tags, status, attempts, correct_count, wrong_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', 0, 0, 0, ?);
            """,
            [
                (
                    c["id"],
                    session_id,
                    int(c["moduleOrder"]),
                    c["moduleTitle"],
                    c["front"],
                    c["back"],
                    c.get("difficulty", "easy"),
                    json.dumps(c.get("tags", [])),
                    now,
                )
                for c in cards
            ],
        )


def _get_next_card(session_id: str) -> Dict | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, module_order, module_title, front, back, difficulty, tags, status, attempts, correct_count, wrong_count
            FROM quiz_cards
            WHERE session_id = ? AND status IN ('new', 'due')
            ORDER BY
              CASE status WHEN 'due' THEN 0 ELSE 1 END,
              wrong_count DESC,
              attempts ASC,
              module_order ASC;
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "cardId": row["id"],
        "moduleOrder": int(row["module_order"]),
        "moduleTitle": row["module_title"],
        "front": row["front"],
        "difficulty": row["difficulty"],
        "tags": json.loads(row["tags"] or "[]"),
        "progress": {
            "status": row["status"],
            "attempts": int(row["attempts"]),
            "correct": int(row["correct_count"]),
            "wrong": int(row["wrong_count"]),
        },
    }


@mcp.tool()
def start_flashcard_quiz(customer_id: int, module_order: int | None = None, limit: int = 30) -> Dict:
    return start_flashcard_quiz_impl(customer_id=customer_id, module_order=module_order, limit=limit)


def start_flashcard_quiz_impl(customer_id: int, module_order: int | None = None, limit: int = 30) -> Dict:
    """Create a persisted flashcard quiz session and return the first card.

    Returns:
        {sessionId, card}
    """

    cards = generate_flashcards_impl(customer_id=customer_id, module_order=module_order, limit=limit)
    session_id = str(uuid.uuid4())

    _persist_quiz_session(session_id=session_id, customer_id=customer_id, module_order=module_order)
    _persist_quiz_cards(session_id=session_id, cards=cards)

    next_card = _get_next_card(session_id)
    return {"sessionId": session_id, "card": next_card, "totalCards": len(cards)}


@mcp.tool()
def get_next_flashcard(session_id: str) -> Dict:
    return get_next_flashcard_impl(session_id=session_id)


def get_next_flashcard_impl(session_id: str) -> Dict:
    """Get the next due/new flashcard (without revealing the back)."""

    card = _get_next_card(session_id)
    if card is None:
        return {"sessionId": session_id, "done": True, "card": None}
    return {"sessionId": session_id, "done": False, "card": card}


@mcp.tool()
def submit_flashcard_answer(session_id: str, card_id: str, answer: str) -> Dict:
    return submit_flashcard_answer_impl(session_id=session_id, card_id=card_id, answer=answer)


def submit_flashcard_answer_impl(session_id: str, card_id: str, answer: str) -> Dict:
    """Grade an answer (deterministic keyword overlap) and advance scheduling.

    Scoring:
      - if score >= 0.6 => correct
      - else => wrong and the card becomes 'due' again
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, front, back, attempts, correct_count, wrong_count
            FROM quiz_cards
            WHERE session_id = ? AND id = ?;
            """,
            (session_id, card_id),
        ).fetchone()

        if row is None:
            raise ValueError("Card not found for this session.")

        expected = row["back"]
        score = _keyword_score(answer, expected)
        correct = bool(score >= 0.6)
        now = _now_date()

        attempts = int(row["attempts"]) + 1
        correct_count = int(row["correct_count"]) + (1 if correct else 0)
        wrong_count = int(row["wrong_count"]) + (0 if correct else 1)

        new_status = "learned" if correct_count >= 1 and correct else "due" if not correct else "learned"

        conn.execute(
            """
            UPDATE quiz_cards
            SET status = ?,
                attempts = ?,
                correct_count = ?,
                wrong_count = ?,
                last_answer = ?,
                updated_at = ?
            WHERE id = ? AND session_id = ?;
            """,
            (new_status, attempts, correct_count, wrong_count, answer, now, card_id, session_id),
        )

        conn.execute(
            "UPDATE quiz_sessions SET updated_at = ? WHERE id = ?;",
            (now, session_id),
        )

    next_card = _get_next_card(session_id)
    return {
        "sessionId": session_id,
        "cardId": card_id,
        "correct": correct,
        "score": score,
        "expected": expected,
        "feedback": "Nice!" if correct else "Not quite — check the answer and try a similar one again.",
        "nextCard": next_card,
        "done": next_card is None,
    }

def _knowledge_question_weight(q_type: str) -> float:
    """Scoring weights requested by user.

    - multiple_choice: 1.0
    - true_false: 0.5
    """

    t = (q_type or "").strip().lower()
    if t in {"tf", "truefalse", "true_false", "true/false"}:
        return 0.5
    return 1.0


def _knowledge_bank_for_module(module_title: str, module_description: str, module_order: int) -> List[Dict]:
    """Deterministic question bank for a single curriculum module.

    Returns 10 questions per module (mixed multiple-choice and true/false).
    This is intentionally LLM-free so tests are stable.
    """

    title_l = (module_title or "").lower()
    desc_l = (module_description or "").lower()

    def qid(suffix: str) -> str:
        return f"kv_m{int(module_order)}_{suffix}"

    if "deduct" in title_l or "deduct" in desc_l:
        topic = "deductible"
    elif "premium" in title_l or "premium" in desc_l:
        topic = "premium"
    elif "claim" in title_l or "claim" in desc_l:
        topic = "claim"
    elif "cover" in title_l or "coverage" in desc_l:
        topic = "coverage"
    else:
        topic = "general"

    def mc(suffix: str, prompt: str, choices: List[str], correct_index: int, explanation: str) -> Dict:
        return {
            "id": qid(suffix),
            "moduleOrder": int(module_order),
            "topic": topic,
            "type": "multiple_choice",
            "prompt": prompt,
            "choices": choices,
            "correctIndex": int(correct_index),
            "expected": choices[int(correct_index)],
            "explanation": explanation,
            "weight": 1.0,
        }

    def tf(suffix: str, statement: str, correct: bool, explanation: str) -> Dict:
        return {
            "id": qid(suffix),
            "moduleOrder": int(module_order),
            "topic": topic,
            "type": "true_false",
            "prompt": f"True/False: {statement}",
            "choices": ["True", "False"],
            "correctIndex": 0 if bool(correct) else 1,
            "expected": "True" if bool(correct) else "False",
            "explanation": explanation,
            "weight": 0.5,
        }

    if topic == "deductible":
        return [
            mc(
                "mc1",
                "What does a deductible mean?",
                [
                    "The amount you pay first on a covered claim",
                    "A discount you always get on repairs",
                    "The maximum your insurer will ever pay",
                    "A fee the other driver pays",
                ],
                0,
                "A deductible is the amount you pay out of pocket before insurance pays the rest of a covered claim.",
            ),
            mc(
                "mc2",
                "Your deductible is $500 and repairs cost $1,800 (covered). How much do you pay?",
                ["$0", "$500", "$1,300", "$1,800"],
                1,
                "You pay the deductible ($500) first; insurance typically covers the remaining $1,300.",
            ),
            mc(
                "mc3",
                "If you raise your deductible, what often happens to your premium?",
                ["It goes up", "It goes down", "It becomes illegal", "It becomes your limit"],
                1,
                "Higher deductibles usually mean lower premiums because you agree to pay more if a claim happens.",
            ),
            mc(
                "mc4",
                "When a deductible applies, it is usually:",
                [
                    "Charged once per claim",
                    "Charged every day",
                    "Charged only if police arrive",
                    "Charged only for liability claims",
                ],
                0,
                "Most deductibles apply per claim (commonly for collision/comprehensive), not per month.",
            ),
            mc(
                "mc5",
                "Which coverage commonly has a deductible?",
                ["Collision", "Liability", "Both always", "Neither"],
                0,
                "Collision/comprehensive commonly have deductibles; liability typically does not.",
            ),
            tf(
                "tf1",
                "A deductible is the amount insurance pays first.",
                False,
                "You pay the deductible first; then insurance pays the remaining covered amount.",
            ),
            tf(
                "tf2",
                "A higher deductible can make your monthly premium lower.",
                True,
                "Often true: you trade a lower premium for higher out-of-pocket cost if a claim happens.",
            ),
            tf(
                "tf3",
                "If repairs cost less than your deductible, insurance usually pays nothing.",
                True,
                "If the claim amount doesn’t exceed the deductible, there’s typically nothing left for insurance to pay.",
            ),
            tf(
                "tf4",
                "You pay your deductible even for excluded (not covered) damage.",
                False,
                "If it’s excluded/not covered, the claim is denied and the deductible usually isn’t the deciding factor.",
            ),
            tf(
                "tf5",
                "Deductibles are chosen when you buy your policy, not when an accident happens.",
                True,
                "You pick deductibles as part of your policy terms upfront.",
            ),
        ]

    if topic == "claim":
        return [
            mc(
                "mc1",
                "What is an insurance claim?",
                [
                    "A request to your insurer to cover/pay for a loss",
                    "A traffic ticket",
                    "Your monthly premium",
                    "A type of deductible",
                ],
                0,
                "A claim is what you file with your insurer to request coverage/payment for a covered loss.",
            ),
            mc(
                "mc2",
                "Which detail helps a claim go smoother?",
                ["Photos and a clear timeline", "Guessing the other driver’s name", "Deleting messages", "Waiting weeks"],
                0,
                "Documentation like photos, locations, and timelines helps insurers evaluate the claim faster.",
            ),
            mc(
                "mc3",
                "Accident vs claim: which statement is correct?",
                ["They mean the same thing", "Accident is the event; claim is what you file", "Claim happens first", "Accident is optional"],
                1,
                "The accident is the event; the claim is the request you submit to your insurance.",
            ),
            mc(
                "mc4",
                "If you’re not sure who is at fault, what should you do?",
                ["Make up a story", "Collect facts and report honestly", "Hide evidence", "Stop cooperating"],
                1,
                "Stick to facts (photos, statements) and let insurers decide fault based on evidence.",
            ),
            mc(
                "mc5",
                "A common first step after a crash is:",
                ["Ensure safety and check injuries", "Argue with the other driver", "Leave immediately", "Post on social media"],
                0,
                "Safety comes first: check for injuries and move to a safe location if possible.",
            ),
            tf("tf1", "Filing a claim always means your insurance will definitely pay.", False,
               "Not always—coverage depends on policy terms, exclusions, and what happened."),
            tf("tf2", "Photos of damage can help support your claim.", True,
               "Photos provide evidence of what happened and the extent of damage."),
            tf("tf3", "A claim is filed with your insurance company (or theirs).", True,
               "Claims are submitted to insurers."),
            tf("tf4", "It’s fine to wait months to report a brand-new accident.", False,
               "Policies often require prompt notice."),
            tf("tf5", "A police report can sometimes help clarify what happened.", True,
               "A report can document facts, especially for serious accidents or disputes."),
        ]

    if topic == "coverage":
        return [
            mc(
                "mc1",
                "What does coverage tell you?",
                [
                    "What the policy will pay for and under what conditions",
                    "Your car’s color",
                    "The other driver’s opinion",
                    "A guaranteed payout amount for any event",
                ],
                0,
                "Coverage defines what’s included (and excluded) and the conditions/limits for payment.",
            ),
            mc(
                "mc2",
                "What is an exclusion?",
                ["Something the policy does NOT cover", "A bonus feature", "A deductible", "A payment plan"],
                0,
                "Exclusions are situations or damage types the policy won’t cover.",
            ),
            mc(
                "mc3",
                "Policy limits are best described as:",
                ["The max the insurer will pay", "The deductible amount", "A ticket limit", "A repair estimate"],
                0,
                "Limits cap how much the insurer can pay.",
            ),
            mc(
                "mc4",
                "State minimum coverage is:",
                ["Always enough", "The legal minimum, not always enough protection", "A luxury upgrade", "Only for teens"],
                1,
                "Minimums meet legal requirements but might not cover all costs in serious accidents.",
            ),
            mc(
                "mc5",
                "If damage is excluded, what happens?",
                ["Insurance pays anyway", "Insurance usually doesn’t pay", "Deductible doubles", "Premium becomes zero"],
                1,
                "Excluded means not covered.",
            ),
            tf("tf1", "Coverage includes limits.", True, "Coverage is defined alongside limits and conditions."),
            tf("tf2", "Exclusions mean 'not covered'.", True, "That’s what exclusions are."),
            tf("tf3", "If something isn’t covered, you can force the insurer to pay by filing anyway.", False,
               "Filing doesn’t create coverage—policy terms control."),
            tf("tf4", "Coverage can differ depending on the policy you bought.", True,
               "Policies vary by selections and endorsements."),
            tf("tf5", "Coverage answers what will be paid for.", True, "That’s the core purpose of coverage."),
        ]

    if topic == "premium":
        return [
            mc(
                "mc1",
                "What is a premium?",
                ["The amount you pay to keep insurance active", "A deductible", "A claim", "A police report"],
                0,
                "Premium is the payment to keep coverage active (monthly/6-month/annual).",
            ),
            mc(
                "mc2",
                "Which factor can raise a premium?",
                ["More risk (tickets/accidents)", "Driving less safely", "Moving to a higher-risk area", "All of the above"],
                3,
                "Premium is tied to risk and coverage.",
            ),
            mc(
                "mc3",
                "If you stop paying premium, what can happen?",
                ["Policy stays active forever", "Policy can lapse/cancel", "Deductible disappears", "Coverage becomes unlimited"],
                1,
                "Nonpayment can lead to lapse/cancellation.",
            ),
            mc(
                "mc4",
                "Premium frequency can be:",
                ["Monthly", "6-month", "Annual", "All of the above"],
                3,
                "Premiums can be billed in different cycles.",
            ),
            mc(
                "mc5",
                "More coverage typically means:",
                ["Lower premium", "Higher premium", "No change", "Illegal"],
                1,
                "More coverage shifts more risk to insurer, often raising premium.",
            ),
            tf("tf1", "Premium is what you pay to keep coverage active.", True, "That’s the definition."),
            tf("tf2", "Riskier driving can increase premium.", True, "Premiums reflect risk."),
            tf("tf3", "Premium and deductible are the same thing.", False, "They are different concepts."),
            tf("tf4", "A premium can be paid monthly.", True, "Common billing cycle."),
            tf("tf5", "If you lapse, you may have no coverage.", True, "That’s the consequence of cancellation/lapse."),
        ]

    return [
        mc(
            "mc1",
            f"Which best describes the main idea of '{module_title}'?",
            [
                "A key insurance concept you should be able to explain",
                "A type of car model",
                "A phone plan",
                "A weather report",
            ],
            0,
            "The module is teaching an insurance concept.",
        ),
        mc(
            "mc2",
            "What should you do if you're unsure what your policy covers?",
            ["Check your policy details (coverage/limits/exclusions)", "Assume it covers everything", "Ignore it", "Wait for an accident"],
            0,
            "Policies define coverage, limits, and exclusions.",
        ),
        mc(
            "mc3",
            "Why do insurers care about risk?",
            ["Because it affects how likely a claim is", "Because it changes the color of your car", "Because it changes the weather", "Because it changes your phone"],
            0,
            "Risk influences pricing and coverage decisions.",
        ),
        mc(
            "mc4",
            "Which is an example of good documentation after an event?",
            ["Photos and notes", "Deleting evidence", "Guessing details", "Making up numbers"],
            0,
            "Evidence helps decisions.",
        ),
        mc(
            "mc5",
            "What’s a good habit as you learn insurance?",
            ["Ask questions and learn key terms", "Avoid reading policy", "Ignore definitions", "Only learn after crashes"],
            0,
            "Learning key terms helps you make better decisions.",
        ),
        tf("tf1", "Insurance terms can affect what you pay.", True, "They impact costs and coverage."),
        tf("tf2", "Policies can include exclusions.", True, "Exclusions define what’s not covered."),
        tf("tf3", "You never need to read your policy.", False, "Reading policy helps you know coverage."),
        tf("tf4", "Good evidence can speed up processes.", True, "Documentation helps."),
        tf("tf5", "Coverage and cost depend on what you purchased.", True, "Your selections matter."),
    ]


@mcp.tool()
def get_knowledge_questions(customer_id: int, limit: int = 3) -> List[Dict]:
    return get_knowledge_questions_impl(customer_id=customer_id, limit=limit)


def get_knowledge_questions_impl(customer_id: int, limit: int = 3, database_path: str | None = None) -> List[Dict]:
    """Return a mixed question bank (MC + True/False) based on the user's curriculum.

    Design notes:
    - Generates 10 questions per curriculum module (so typically 10–20+ total depending on modules)
    - Multiple-choice questions are worth 1 point; True/False are worth 0.5 points

    Args:
        customer_id: Customer id whose curriculum we use
        limit: Maximum number of questions to return
    """

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        curriculum = get_curriculum_impl(int(customer_id))
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path

    bank: List[Dict] = []
    for m in curriculum:
        bank.extend(
            _knowledge_bank_for_module(
                module_title=str(m.get("module")),
                module_description=str(m.get("description")),
                module_order=int(m.get("order")),
            )
        )

    bank.sort(key=lambda q: (int(q.get("moduleOrder", 0)), str(q.get("id", ""))))

    return bank[: int(limit)]


@mcp.tool()
def grade_knowledge_answer(customer_id: int, question_id: str, answer: str) -> Dict:
    return grade_knowledge_answer_impl(customer_id=customer_id, question_id=question_id, answer=answer)


def grade_knowledge_answer_impl(
    customer_id: int,
    question_id: str,
    answer: str,
    database_path: str | None = None,
) -> Dict:
    """Grade a knowledge validation answer and log a feedback event."""

    bank = get_knowledge_questions_impl(int(customer_id), limit=200, database_path=database_path)
    q = next((x for x in bank if x["id"] == question_id), None)
    if not q:
        raise ValueError("Unknown question_id")

    expected = str(q.get("expected", ""))
    q_type = str(q.get("type", "multiple_choice"))
    weight = float(q.get("weight", _knowledge_question_weight(q_type)))


    ans = (answer or "").strip()
    ans_l = ans.lower().strip()

    choices: List[str] = list(q.get("choices", []))
    correct_index = int(q.get("correctIndex", 0))

    selected_index: int | None = None
    if q_type == "true_false":
        if ans_l in {"t", "true"}:
            selected_index = 0
        elif ans_l in {"f", "false"}:
            selected_index = 1
        else:
            if ans_l == "true":
                selected_index = 0
            elif ans_l == "false":
                selected_index = 1
    else:
        if ans_l in {"a", "b", "c", "d"}:
            selected_index = {"a": 0, "b": 1, "c": 2, "d": 3}[ans_l]
        elif ans_l.isdigit():
            n = int(ans_l)
            if 1 <= n <= len(choices):
                selected_index = n - 1
        else:
            for idx, c in enumerate(choices):
                if ans_l == str(c).lower().strip():
                    selected_index = idx
                    break

    correct = selected_index is not None and int(selected_index) == int(correct_index)
    score = float(weight if correct else 0.0)

    try:
        log_feedback_event_impl(
            customer_id=customer_id,
            agent_name="knowledge_validation",
            event_type="graded",
            payload={
                "questionId": question_id,
                "type": q_type,
                "weight": weight,
                "score": score,
                "correct": correct,
            },
        )
    except Exception:
        pass

    return {
        "customerId": int(customer_id),
        "questionId": question_id,
        "correct": correct,
        "score": score,
        "weight": weight,
        "type": q_type,
        "expected": expected,
        "feedback": "Nice!" if correct else "Not quite — review the concept and try again.",
        "explanation": q.get("explanation", ""),
    }


def _get_plan_id_for_customer(customer_id: int, database_path: str | None = None) -> int:
    with _connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id FROM curriculum_plans WHERE customer_id = ?;", (int(customer_id),)
        ).fetchone()
    if row is None:
        raise ValueError("No curriculum plan found for this customer.")
    return int(row["id"])


@mcp.tool()
def start_knowledge_quiz_attempt(customer_id: int, questions_limit: int = 10) -> Dict:
    return start_knowledge_quiz_attempt_impl(customer_id=customer_id, questions_limit=questions_limit)


def start_knowledge_quiz_attempt_impl(
    customer_id: int,
    questions_limit: int = 10,
    database_path: str | None = None,
) -> Dict:
    """Create a knowledge validation quiz attempt tied to the customer's curriculum plan.

    This enables saving scores and unlimited reattempts.
    """

    plan_id = _get_plan_id_for_customer(int(customer_id), database_path=database_path)
    attempt_id = str(uuid.uuid4())
    now = _now_date()

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        qs = get_knowledge_questions_impl(int(customer_id), limit=int(questions_limit))
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path
    points_possible = float(sum(float(q.get("weight", _knowledge_question_weight(q.get("type", "")))) for q in qs))

    with _connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_quiz_attempts
              (id, customer_id, plan_id, created_at, questions_count, points_possible, points_earned, mode)
            VALUES
              (?, ?, ?, ?, ?, ?, 0.0, 'question_bank');
            """,
            (
                attempt_id,
                int(customer_id),
                int(plan_id),
                now,
                int(len(qs)),
                float(points_possible),
            ),
        )

    return {
        "attemptId": attempt_id,
        "customerId": int(customer_id),
        "planId": int(plan_id),
        "questionsCount": int(len(qs)),
        "pointsPossible": float(points_possible),
        "createdAt": now,
    }


@mcp.tool()
def record_knowledge_quiz_answer(customer_id: int, attempt_id: str, question_id: str, answer: str) -> Dict:
    return record_knowledge_quiz_answer_impl(
        customer_id=customer_id, attempt_id=attempt_id, question_id=question_id, answer=answer
    )


def record_knowledge_quiz_answer_impl(
    customer_id: int,
    attempt_id: str,
    question_id: str,
    answer: str,
    database_path: str | None = None,
) -> Dict:
    """Grade + persist a single answer for a given attempt.

    Allows reattempts by simply creating a new attempt id.
    """

    with _connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        attempt = conn.execute(
            "SELECT id, customer_id, plan_id FROM knowledge_quiz_attempts WHERE id = ?;",
            (str(attempt_id),),
        ).fetchone()
    if attempt is None or int(attempt["customer_id"]) != int(customer_id):
        raise ValueError("Unknown attempt_id")

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        graded = grade_knowledge_answer_impl(customer_id=int(customer_id), question_id=question_id, answer=answer)
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        bank = get_knowledge_questions_impl(int(customer_id), limit=200)
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path
    q = next((x for x in bank if x["id"] == question_id), None)
    if not q:
        raise ValueError("Unknown question_id")

    module_order = q.get("moduleOrder")
    q_type = str(q.get("type", "multiple_choice"))
    weight = float(q.get("weight", _knowledge_question_weight(q_type)))
    points_earned = float(graded.get("score", 0.0))
    correct = 1 if bool(graded.get("correct")) else 0
    now = _now_date()

    result_id = str(uuid.uuid4())
    with _connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_quiz_results
              (id, attempt_id, question_id, module_order, question_type, weight, answer_text, correct, points_earned, created_at)
            VALUES
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                result_id,
                str(attempt_id),
                str(question_id),
                int(module_order) if module_order is not None else None,
                q_type,
                float(weight),
                str(answer),
                int(correct),
                float(points_earned),
                now,
            ),
        )

        total = conn.execute(
            "SELECT COALESCE(SUM(points_earned), 0.0) AS total FROM knowledge_quiz_results WHERE attempt_id = ?;",
            (str(attempt_id),),
        ).fetchone()[0]
        conn.execute(
            "UPDATE knowledge_quiz_attempts SET points_earned = ? WHERE id = ?;",
            (float(total), str(attempt_id)),
        )

    return {
        "attemptId": str(attempt_id),
        "resultId": result_id,
        **graded,
    }


@mcp.tool()
def get_knowledge_quiz_attempts(customer_id: int, limit: int = 20) -> List[Dict]:
    return get_knowledge_quiz_attempts_impl(customer_id=customer_id, limit=limit)


def get_knowledge_quiz_attempts_impl(customer_id: int, limit: int = 20, database_path: str | None = None) -> List[Dict]:
    """List recent knowledge quiz attempts for a customer (reattempt history)."""

    with _connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, plan_id, created_at, questions_count, points_possible, points_earned
            FROM knowledge_quiz_attempts
            WHERE customer_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (int(customer_id), int(limit)),
        ).fetchall()

    return [
        {
            "attemptId": r["id"],
            "planId": int(r["plan_id"]),
            "createdAt": r["created_at"],
            "questionsCount": int(r["questions_count"]),
            "pointsPossible": float(r["points_possible"]),
            "pointsEarned": float(r["points_earned"]),
        }
        for r in rows
    ]

#for, Resource Recommendation Agent, to be determined
@mcp.tool()
def recommend_resources(customer_id: int, topic: str, state: str | None = None, limit: int = 5) -> List[Dict]:
    return recommend_resources_impl(customer_id=customer_id, topic=topic, state=state, limit=limit)


def recommend_resources_impl(customer_id: int, topic: str, state: str | None = None, limit: int = 5) -> List[Dict]:
    """Return curated, state-aware resources (deterministic, no external calls).

    Contract:
    - Uses the customer's saved state when `state` isn't provided.
    - Produces simple, deterministic resource cards with the state encoded in titles/summaries.
    - Persists the result list to `recommended_resources`.
    """

    if state is None:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT state FROM customers WHERE id = ?;", (int(customer_id),)).fetchone()
        state = row["state"] if row else None

    t = (topic or "").strip().lower()
    st = (state or "").strip().upper() if state else ""

    base = [
        {
            "type": "video",
            "title": "Auto insurance basics in 5 minutes",
            "summary": "A quick explanation of premium, deductible, and coverage with simple examples.",
            "url": "https://www.naic.org/consumer.htm",
        },
        {
            "type": "article",
            "title": "How claims work (step-by-step)",
            "summary": "What to do after an accident, what info to collect, and when to contact your insurer.",
            "url": "https://www.usa.gov/insurance",
        },
    ]

    by_topic: List[Dict] = []
    if "deduct" in t:
        by_topic.append(
            {
                "type": "video",
                "title": "Deductibles explained with examples",
                "summary": "See how a $500 deductible changes what you pay on a claim.",
                "url": "https://www.iii.org/",
            }
        )
    if "claim" in t:
        by_topic.append(
            {
                "type": "checklist",
                "title": "Accident checklist (what to collect)",
                "summary": "Photos, other driver's info, witness notes, police report, and timeline.",
                "url": "https://www.usa.gov/",
            }
        )
    if "coverage" in t:
        by_topic.append(
            {
                "type": "article",
                "title": "Understanding liability vs collision vs comprehensive",
                "summary": "A simple breakdown of common coverage types and what they generally pay for.",
                "url": "https://www.naic.org/",
            }
        )

    state_note: List[Dict] = []
    if st:
        kw = f"{st} {t}".strip()
        state_note.extend(
            [
                {
                    "type": "state",
                    "title": f"{st} insurance department (official requirements + complaints)",
                    "summary": f"Use keywords like '{kw} minimum coverage' and '{kw} file complaint' when searching official sources.",
                    "url": "https://content.naic.org/state-insurance-departments",
                },
                {
                    "type": "article",
                    "title": f"{st}: common '{t}' questions (what locals ask most)",
                    "summary": f"A state-scoped checklist of what to verify for '{t}' (limits, deductibles, timelines).",
                    "url": "https://www.usa.gov/insurance",
                },
            ]
        )

    resources = (by_topic + base + state_note)[: int(limit)]

    for r in resources:
        r.setdefault("type", "article")
        r.setdefault("title", "Resource")
        r.setdefault("summary", "")
        r.setdefault("url", "")

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO recommended_resources (id, customer_id, created_at, state, topic, resources_json)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (str(uuid.uuid4()), int(customer_id), now, st or None, topic, json.dumps(resources)),
        )

    log_feedback_event_impl(
        customer_id=customer_id,
        agent_name="resource_recommendation",
        event_type="recommended",
        payload={"topic": topic, "state": st, "count": len(resources)},
    )

    return resources


def summarize_resources_impl(resources: List[Dict], style: str = "general") -> Dict:
    """Generate a one-paragraph deterministic summary for a list of resources.

    style:
      - 'general': summary across all resources
      - 'video': a short 'video-style' summary for a single resource
    """

    items = resources or []
    if not items:
        return {"style": style, "summary": "No resources found."}

    if style == "video":
        r = items[0]
        title = (r.get("title") or "this resource").strip()
        summary = (r.get("summary") or "").strip()
        video = (
            f"In this quick video, we cover {title}. "
            f"Main takeaway: {summary or 'focus on the key steps and definitions.'} "
            f"At the end, you should know what to do next and what details matter most."
        )
        return {"style": style, "summary": video}

    titles = [str(r.get("title") or "").strip() for r in items if str(r.get("title") or "").strip()]
    titles = titles[:5]
    joined = "; ".join(titles)
    general = (
        "Here are the key resources you can use right now: "
        f"{joined}. "
        "Together, they explain the basics, what to collect or verify, and where to find official state guidance."
    )
    return {"style": style, "summary": general}

#for, Accident Reporting Agent 


@mcp.tool()
def start_accident_report(customer_id: int) -> Dict:
    return start_accident_report_impl(customer_id=customer_id)


def start_accident_report_impl(customer_id: int) -> Dict:
    """Create a new accident report (case) and return its id."""

    report_id = str(uuid.uuid4())
    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            INSERT INTO accident_reports (id, customer_id, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, 'collecting');
            """,
            (report_id, int(customer_id), now, now),
        )

    log_feedback_event_impl(
        customer_id=customer_id,
        agent_name="accident_reporting",
        event_type="created",
        payload={"reportId": report_id},
    )

    return {
        "reportId": report_id,
        "status": "collecting",
        "nextQuestions": [
            "Is anyone injured? If yes, how many?",
            "What's your location (city / nearest intersection)?",
            "Is the vehicle drivable?",
            "Upload photo/video evidence URLs (if any).",
        ],
    }


@mcp.tool()
def update_accident_report(
    report_id: str,
    location: str | None = None,
    injured_count: int | None = None,
    vehicles_drivable: bool | None = None,
    evidence_urls: List[str] | None = None,
    notes: str | None = None,
) -> Dict:
    return update_accident_report_impl(
        report_id=report_id,
        location=location,
        injured_count=injured_count,
        vehicles_drivable=vehicles_drivable,
        evidence_urls=evidence_urls,
        notes=notes,
    )


def update_accident_report_impl(
    report_id: str,
    location: str | None = None,
    injured_count: int | None = None,
    vehicles_drivable: bool | None = None,
    evidence_urls: List[str] | None = None,
    notes: str | None = None,
) -> Dict:
    """Update accident report details."""

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if existing is None:
            raise ValueError("report_id not found")

        merged_evidence = json.loads(existing["evidence_urls"] or "[]")
        if evidence_urls:
            for u in evidence_urls:
                if u and u not in merged_evidence:
                    merged_evidence.append(u)

        conn.execute(
            """
            UPDATE accident_reports
            SET location = COALESCE(?, location),
                injured_count = COALESCE(?, injured_count),
                vehicles_drivable = COALESCE(?, vehicles_drivable),
                notes = COALESCE(?, notes),
                evidence_urls = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (
                location,
                int(injured_count) if injured_count is not None else None,
                1 if vehicles_drivable is True else 0 if vehicles_drivable is False else None,
                notes,
                json.dumps(merged_evidence),
                now,
                report_id,
            ),
        )

        updated = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()

    log_feedback_event_impl(
        customer_id=int(updated["customer_id"]),
        agent_name="accident_reporting",
        event_type="updated",
        payload={"reportId": report_id},
    )

    return {
        "reportId": report_id,
        "customerId": int(updated["customer_id"]),
        "location": updated["location"],
        "injuredCount": int(updated["injured_count"] or 0),
        "vehiclesDrivable": None if updated["vehicles_drivable"] is None else bool(updated["vehicles_drivable"]),
        "evidenceUrls": json.loads(updated["evidence_urls"] or "[]"),
        "notes": updated["notes"],
        "status": updated["status"],
        "updatedAt": updated["updated_at"],
    }


@mcp.tool()
def finalize_accident_report(report_id: str) -> Dict:
    return finalize_accident_report_impl(report_id=report_id)


def finalize_accident_report_impl(report_id: str) -> Dict:
    """Mark the report as ready for assessment."""

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if row is None:
            raise ValueError("report_id not found")
        conn.execute(
            "UPDATE accident_reports SET status='ready', updated_at=? WHERE id=?;",
            (now, report_id),
        )

    return {"reportId": report_id, "status": "ready", "updatedAt": now}

#for, Accident Severity Assesment Agent
def _assess_severity(injured_count: int, vehicles_drivable: bool | None, notes: str | None) -> Dict:
    notes_l = (notes or "").lower()
    accident_type = "unknown"
    if "rear" in notes_l and "end" in notes_l:
        accident_type = "rear-end"
    elif "side" in notes_l or "t-bone" in notes_l:
        accident_type = "side-impact"
    elif "roll" in notes_l:
        accident_type = "rollover"

    if int(injured_count) > 0:
        return {
            "severity": "high",
            "urgency": "emergency",
            "accidentType": accident_type,
            "rationale": "Injuries reported — prioritize medical help and emergency services.",
            "recommended": [
                "Call emergency services if needed",
                "Move to a safe location if possible",
                "Document the scene when safe",
            ],
        }

    if vehicles_drivable is False:
        return {
            "severity": "medium",
            "urgency": "soon",
            "accidentType": accident_type,
            "rationale": "No injuries, but vehicle not drivable — towing and prompt reporting recommended.",
            "recommended": [
                "Arrange towing / roadside assistance",
                "Take photos and exchange information",
                "Report to your insurer",
            ],
        }

    return {
        "severity": "low",
        "urgency": "routine",
        "accidentType": accident_type,
        "rationale": "No injuries reported and vehicle appears drivable — proceed with documentation and reporting.",
        "recommended": [
            "Take photos and exchange information",
            "Report to your insurer",
            "Save receipts and notes",
        ],
    }


@mcp.tool()
def assess_accident_severity(report_id: str) -> Dict:
    return assess_accident_severity_impl(report_id=report_id)


def assess_accident_severity_impl(report_id: str) -> Dict:
    """Compute and persist an accident severity assessment."""

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if report is None:
            raise ValueError("report_id not found")

        vehicles_drivable = None if report["vehicles_drivable"] is None else bool(report["vehicles_drivable"])
        result = _assess_severity(
            injured_count=int(report["injured_count"] or 0),
            vehicles_drivable=vehicles_drivable,
            notes=report["notes"],
        )

        assessment_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO severity_assessments (id, report_id, created_at, severity, accident_type, urgency, rationale, recommended_actions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
              severity=excluded.severity,
              accident_type=excluded.accident_type,
              urgency=excluded.urgency,
              rationale=excluded.rationale,
              recommended_actions=excluded.recommended_actions;
            """,
            (
                assessment_id,
                report_id,
                now,
                result["severity"],
                result.get("accidentType"),
                result["urgency"],
                result["rationale"],
                json.dumps(result["recommended"]),
            ),
        )

    log_feedback_event_impl(
        customer_id=int(report["customer_id"]),
        agent_name="accident_severity",
        event_type="assessed",
        payload={"reportId": report_id, "severity": result["severity"], "urgency": result["urgency"]},
    )

    return {
        "reportId": report_id,
        "severity": result["severity"],
        "urgency": result["urgency"],
        "accidentType": result.get("accidentType"),
        "rationale": result["rationale"],
        "recommendedActions": result["recommended"],
    }

#for, Policy Interpretation Agent
@mcp.tool()
def interpret_policy(report_id: str) -> Dict:
    return interpret_policy_impl(report_id=report_id)


def interpret_policy_impl(report_id: str) -> Dict:
    """Create a simple coverage/deductible expectation from stored customer profile."""

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if report is None:
            raise ValueError("report_id not found")
        cust = conn.execute(
            "SELECT * FROM customers WHERE id = ?;",
            (int(report["customer_id"]),),
        ).fetchone()
        if cust is None:
            raise ValueError("customer for report not found")

        coverage_type = (cust["coverage_type"] or "").strip().lower()

        assumptions = []
        exclusions = []
        estimated_deductible = 500.0 if "full" in coverage_type else 0.0
        if "liability" in coverage_type and "full" not in coverage_type:
            coverage_summary = (
                "Liability coverage generally helps pay for damage/injuries you cause to others. "
                "It usually does not pay for your own vehicle repairs."
            )
            exclusions.append("Your own vehicle damage may not be covered under liability-only policies")
            estimated_out = None
        else:
            coverage_summary = (
                "Full coverage typically includes liability plus collision/comprehensive options. "
                "Your own vehicle damage may be covered (subject to deductible and exclusions)."
            )
            assumptions.append("Assuming collision coverage applies to this accident")
            estimated_out = estimated_deductible

        interpretation_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO policy_interpretations (id, report_id, created_at, coverage_summary, estimated_deductible, estimated_out_of_pocket, assumptions, exclusions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
              coverage_summary=excluded.coverage_summary,
              estimated_deductible=excluded.estimated_deductible,
              estimated_out_of_pocket=excluded.estimated_out_of_pocket,
              assumptions=excluded.assumptions,
              exclusions=excluded.exclusions;
            """,
            (
                interpretation_id,
                report_id,
                now,
                coverage_summary,
                float(estimated_deductible) if estimated_deductible is not None else None,
                float(estimated_out) if estimated_out is not None else None,
                json.dumps(assumptions),
                json.dumps(exclusions),
            ),
        )

    log_feedback_event_impl(
        customer_id=int(report["customer_id"]),
        agent_name="policy_interpretation",
        event_type="interpreted",
        payload={"reportId": report_id, "coverageType": cust["coverage_type"]},
    )

    return {
        "reportId": report_id,
        "coverageType": cust["coverage_type"],
        "summary": coverage_summary,
        "estimatedDeductible": estimated_deductible,
        "estimatedOutOfPocket": estimated_out,
        "assumptions": assumptions,
        "exclusions": exclusions,
    }

#for, Claims Preparation Agent
@mcp.tool()
def prepare_claim_packet(report_id: str) -> Dict:
    return prepare_claim_packet_impl(report_id=report_id)


def prepare_claim_packet_impl(report_id: str) -> Dict:
    """Create a claim-ready packet and list missing fields."""

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if report is None:
            raise ValueError("report_id not found")
        customer = conn.execute("SELECT * FROM customers WHERE id=?;", (int(report["customer_id"]),)).fetchone()

        missing = []
        if not report["location"]:
            missing.append("location")
        if report["vehicles_drivable"] is None:
            missing.append("vehicles_drivable")
        evidence = json.loads(report["evidence_urls"] or "[]")
        if not evidence:
            missing.append("evidence_urls")

        packet = {
            "customer": {
                "id": int(customer["id"]) if customer else int(report["customer_id"]),
                "name": (customer["name"] if customer else None),
                "state": (customer["state"] if customer else None),
                "vehicle": (customer["vehicle_name"] if customer else None),
                "coverageType": (customer["coverage_type"] if customer else None),
            },
            "accident": {
                "reportId": report_id,
                "location": report["location"],
                "injuredCount": int(report["injured_count"] or 0),
                "vehiclesDrivable": None
                if report["vehicles_drivable"] is None
                else bool(report["vehicles_drivable"]),
                "notes": report["notes"],
                "evidenceUrls": evidence,
            },
            "createdAt": now,
        }

        packet_id = str(uuid.uuid4())
        status = "ready" if not missing else "draft"

        conn.execute(
            """
            INSERT INTO claim_packets (id, report_id, created_at, status, missing_items, packet_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
              status=excluded.status,
              missing_items=excluded.missing_items,
              packet_json=excluded.packet_json;
            """,
            (packet_id, report_id, now, status, json.dumps(missing), json.dumps(packet)),
        )

    log_feedback_event_impl(
        customer_id=int(report["customer_id"]),
        agent_name="claims_preparation",
        event_type="prepared",
        payload={"reportId": report_id, "status": status, "missing": missing},
    )

    return {"reportId": report_id, "status": status, "missingItems": missing, "packet": packet}

#for, Action Plan Agent 
@mcp.tool()
def generate_action_plan(report_id: str) -> Dict:
    return generate_action_plan_impl(report_id=report_id)


def generate_action_plan_impl(report_id: str) -> Dict:
    """Generate next steps + simple timelines for this report."""

    now = _now_date()
    severity = None
    policy = None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("SELECT * FROM accident_reports WHERE id=?;", (report_id,)).fetchone()
        if report is None:
            raise ValueError("report_id not found")

        sev = conn.execute("SELECT * FROM severity_assessments WHERE report_id=?;", (report_id,)).fetchone()
        if sev is not None:
            severity = sev["severity"]

        pol = conn.execute("SELECT * FROM policy_interpretations WHERE report_id=?;", (report_id,)).fetchone()
        if pol is not None:
            policy = pol["coverage_summary"]

        steps = []
        if int(report["injured_count"] or 0) > 0:
            steps.append({"step": "Get medical help / call emergency services if needed", "priority": "high"})
        steps.extend(
            [
                {"step": "Ensure everyone is safe and move to a safe spot if possible", "priority": "high"},
                {"step": "Document the scene (photos, videos, notes, witness info)", "priority": "high"},
                {"step": "Exchange insurance/contact information", "priority": "high"},
                {"step": "Notify your insurer and start a claim", "priority": "medium"},
                {"step": "Get repair estimates / towing if needed", "priority": "medium"},
            ]
        )

        timelines = [
            {"when": "Now", "what": "Safety + initial documentation"},
            {"when": "Today", "what": "Report to insurer; secure towing/repairs"},
            {"when": "Next few days", "what": "Adjuster contact; estimates; repairs scheduling"},
        ]

        plan_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO action_plans (id, report_id, created_at, steps_json, timelines_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
              steps_json=excluded.steps_json,
              timelines_json=excluded.timelines_json;
            """,
            (plan_id, report_id, now, json.dumps(steps), json.dumps(timelines)),
        )

    log_feedback_event_impl(
        customer_id=int(report["customer_id"]),
        agent_name="action_plan",
        event_type="generated",
        payload={"reportId": report_id, "severity": severity},
    )

    return {
        "reportId": report_id,
        "severity": severity,
        "policySummary": policy,
        "steps": steps,
        "timelines": timelines,
    }

#for, Escalation & Routing Agent
@mcp.tool()
def escalate_and_route(report_id: str) -> Dict:
    return escalate_and_route_impl(report_id=report_id)


def escalate_and_route_impl(report_id: str) -> Dict:
    """Route to humans/emergency when criteria indicate it."""

    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("SELECT * FROM accident_reports WHERE id=?;", (report_id,)).fetchone()
        if report is None:
            raise ValueError("report_id not found")

        sev = conn.execute("SELECT * FROM severity_assessments WHERE report_id=?;", (report_id,)).fetchone()
        severity = sev["severity"] if sev else None
        urgency = sev["urgency"] if sev else None

        injured = int(report["injured_count"] or 0)
        if injured > 0 or (urgency == "emergency"):
            reason = "Injuries reported"
            routed_to = "emergency_services"
        elif severity == "medium":
            reason = "Vehicle not drivable / needs towing support"
            routed_to = "human_adjuster"
        else:
            reason = "Self-serve supported"
            routed_to = "self_serve"

        summary = (
            f"Accident report {report_id}: location={report['location']}, injured={injured}, "
            f"drivable={report['vehicles_drivable']}, severity={severity}, urgency={urgency}"
        )

        escalation_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO escalations (id, report_id, created_at, reason, routed_to, summary)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (escalation_id, report_id, now, reason, routed_to, summary),
        )

    log_feedback_event_impl(
        customer_id=int(report["customer_id"]),
        agent_name="escalation_and_routing",
        event_type="routed",
        payload={"reportId": report_id, "routedTo": routed_to, "reason": reason},
    )

    return {"reportId": report_id, "routedTo": routed_to, "reason": reason, "summary": summary}

#for, Continuous Improvement & Feedback Agent
@mcp.tool()
def log_feedback_event(customer_id: int | None, agent_name: str, event_type: str, payload: Dict | None = None) -> Dict:
    return log_feedback_event_impl(customer_id=customer_id, agent_name=agent_name, event_type=event_type, payload=payload)


def log_feedback_event_impl(customer_id: int | None, agent_name: str, event_type: str, payload: Dict | None = None) -> Dict:
    """Persist a feedback/telemetry event (no PII beyond customer_id)."""

    event_id = str(uuid.uuid4())
    now = _now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO feedback_events (id, created_at, customer_id, agent_name, event_type, payload_json)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                event_id,
                now,
                int(customer_id) if customer_id is not None else None,
                agent_name,
                event_type,
                json.dumps(payload or {}),
            ),
        )
    return {"id": event_id, "createdAt": now, "customerId": customer_id, "agent": agent_name, "type": event_type}


@mcp.tool()
def get_feedback_summary(customer_id: int, limit: int = 50) -> Dict:
    return get_feedback_summary_impl(customer_id=customer_id, limit=limit)


def get_feedback_summary_impl(customer_id: int, limit: int = 50) -> Dict:
    """Simple summary of feedback events for a customer."""

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT agent_name, event_type, payload_json, created_at
            FROM feedback_events
            WHERE customer_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (int(customer_id), int(limit)),
        ).fetchall()

    counts: Dict[str, int] = {}
    for r in rows:
        key = f"{r['agent_name']}:{r['event_type']}"
        counts[key] = counts.get(key, 0) + 1

    return {
        "customerId": int(customer_id),
        "totalEvents": len(rows),
        "counts": counts,
        "recent": [
            {
                "agent": r["agent_name"],
                "type": r["event_type"],
                "createdAt": r["created_at"],
                "payload": json.loads(r["payload_json"] or "{}"),
            }
            for r in rows
        ],
    }

#to run the mcp
if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "http").strip().lower()
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        stateless = os.getenv("MCP_STATELESS_HTTP", "false").strip().lower() in {"1", "true", "yes", "on"}
        mcp.run(
            transport="http",
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8000")),
            stateless_http=stateless,
        )