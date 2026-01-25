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

#for Knowledge Validation, to be determined


def _default_knowledge_questions() -> List[Dict]:
    """Deterministic mini-scenarios used for knowledge validation."""

    return [
        {
            "id": "kv1",
            "topic": "deductible",
            "scenario": "Your deductible is $500 and repairs cost $1,800 (covered). What do you pay?",
            "expected": "You pay $500 out of pocket and insurance pays the rest",
        },
        {
            "id": "kv2",
            "topic": "claim",
            "scenario": "You got rear-ended. What is a 'claim' in this situation?",
            "expected": "A request to your insurer to pay for a covered loss",
        },
        {
            "id": "kv3",
            "topic": "coverage",
            "scenario": "True/False: If something is excluded, insurance still pays if you ask.",
            "expected": "False",
        },
    ]


@mcp.tool()
def get_knowledge_questions(customer_id: int, limit: int = 3) -> List[Dict]:
    return get_knowledge_questions_impl(customer_id=customer_id, limit=limit)


def get_knowledge_questions_impl(customer_id: int, limit: int = 3) -> List[Dict]:
    """Return short scenario questions for knowledge validation."""
    qs = _default_knowledge_questions()
    return qs[: int(limit)]


@mcp.tool()
def grade_knowledge_answer(customer_id: int, question_id: str, answer: str) -> Dict:
    return grade_knowledge_answer_impl(customer_id=customer_id, question_id=question_id, answer=answer)


def grade_knowledge_answer_impl(customer_id: int, question_id: str, answer: str) -> Dict:
    """Grade a knowledge validation answer and log a feedback event."""

    q = next((x for x in _default_knowledge_questions() if x["id"] == question_id), None)
    if not q:
        raise ValueError("Unknown question_id")

    expected = q["expected"]
    score = _keyword_score(answer, expected)
    correct = bool(score >= 0.6)

    log_feedback_event_impl(
        customer_id=customer_id,
        agent_name="knowledge_validation",
        event_type="graded",
        payload={"questionId": question_id, "score": score, "correct": correct},
    )

    return {
        "customerId": int(customer_id),
        "questionId": question_id,
        "correct": correct,
        "score": score,
        "expected": expected,
        "feedback": "Nice!" if correct else "Not quite — review the concept and try again.",
    }

#for, Resource Recommendation Agent, to be determined


@mcp.tool()
def recommend_resources(customer_id: int, topic: str, state: str | None = None, limit: int = 5) -> List[Dict]:
    return recommend_resources_impl(customer_id=customer_id, topic=topic, state=state, limit=limit)


def recommend_resources_impl(customer_id: int, topic: str, state: str | None = None, limit: int = 5) -> List[Dict]:
    """Return curated, state-aware resources (deterministic, no external calls)."""

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
        state_note.append(
            {
                "type": "state",
                "title": f"{st} insurance department (find official state resources)",
                "summary": "Look up your state's department of insurance for minimum requirements and complaint options.",
                "url": "https://content.naic.org/state-insurance-departments",
            }
        )

    resources = (by_topic + base + state_note)[: int(limit)]

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