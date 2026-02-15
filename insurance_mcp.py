from fastmcp import FastMCP
from typing import List, Dict
from datetime import datetime, timezone
import sqlite3
import json
import uuid
import re
from io import BytesIO
from pathlib import Path

from database.insurance_db import init_db
import os

try:
    from pypdf import PdfWriter
except Exception:  
    PdfWriter = None  

db_path = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))
mcp = FastMCP("AutoInsuranceMCP")
init_db(db_path)


def connect(database_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection to the configured DB (or an override).

    Tests use `database_path` to isolate state in a tmp db.
    """

    path = database_path or db_path
    init_db(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_teacher_views_schema(database_path: str | None = None) -> None:
    """Best-effort schema init for teacher module view history."""

    with connect(database_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teacher_module_views (
              id TEXT PRIMARY KEY,
              customer_id INTEGER NOT NULL,
              module_order INTEGER NOT NULL,
              module_title TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
              FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_teacher_views_customer ON teacher_module_views(customer_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_teacher_views_module ON teacher_module_views(customer_id, module_order);"
        )


def ensure_knowledge_validation_views_schema(database_path: str | None = None) -> None:
    """Best-effort schema init for knowledge-validation module selection history."""

    with connect(database_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_validation_module_views (
              id TEXT PRIMARY KEY,
              customer_id INTEGER NOT NULL,
              module_order INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
              FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kvmv_customer ON knowledge_validation_module_views(customer_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kvmv_module ON knowledge_validation_module_views(customer_id, module_order);"
        )


def record_teacher_module_view_impl(
    *,
    customer_id: int,
    module_order: int,
    module_title: str,
    database_path: str | None = None,
) -> Dict:
    """Persist that a customer viewed a given module in the Teacher Agent.

    This is append-only (we keep history) and does NOT prevent repeats.
    """

    ensure_teacher_views_schema(database_path)
    view_id = str(uuid.uuid4())
    now = now_date()

    with connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO teacher_module_views (id, customer_id, module_order, module_title, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (view_id, int(customer_id), int(module_order), str(module_title), now),
        )

    return {
        "viewId": view_id,
        "customerId": int(customer_id),
        "moduleOrder": int(module_order),
        "moduleTitle": str(module_title),
        "createdAt": now,
    }


def record_knowledge_validation_module_view_impl(
    *,
    customer_id: int,
    module_order: int,
    database_path: str | None = None,
) -> Dict:
    """Persist that a customer selected a module in the Knowledge Validation Agent.

    This is append-only (we keep history) and does NOT prevent repeats.
    """

    ensure_knowledge_validation_views_schema(database_path)
    view_id = str(uuid.uuid4())
    now = now_date()

    with connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_validation_module_views (id, customer_id, module_order, created_at)
            VALUES (?, ?, ?, ?);
            """,
            (view_id, int(customer_id), int(module_order), now),
        )

    return {
        "viewId": view_id,
        "customerId": int(customer_id),
        "moduleOrder": int(module_order),
        "createdAt": now,
    }


@mcp.tool()
def record_knowledge_validation_module_view(customer_id: int, module_order: int) -> Dict:
    return record_knowledge_validation_module_view_impl(
        customer_id=int(customer_id), module_order=int(module_order)
    )


def get_knowledge_validation_module_views_impl(
    *,
    customer_id: int,
    limit: int = 50,
    database_path: str | None = None,
) -> List[Dict]:
    """Return recent knowledge validation module selections for a customer."""

    ensure_knowledge_validation_views_schema(database_path)

    with connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, customer_id, module_order, created_at
            FROM knowledge_validation_module_views
            WHERE customer_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (int(customer_id), int(limit)),
        ).fetchall()

    return [
        {
            "viewId": r["id"],
            "customerId": int(r["customer_id"]),
            "moduleOrder": int(r["module_order"]),
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


@mcp.tool()
def get_knowledge_validation_module_views(customer_id: int, limit: int = 50) -> List[Dict]:
    return get_knowledge_validation_module_views_impl(customer_id=int(customer_id), limit=int(limit))


def get_last_knowledge_validation_module_impl(
    customer_id: int, database_path: str | None = None
) -> Dict | None:
    views = get_knowledge_validation_module_views_impl(
        customer_id=int(customer_id), limit=1, database_path=database_path
    )
    if not views:
        return None
    return views[0]


@mcp.tool()
def get_last_knowledge_validation_module(customer_id: int) -> Dict | None:
    return get_last_knowledge_validation_module_impl(customer_id=int(customer_id))


@mcp.tool()
def record_teacher_module_view(customer_id: int, module_order: int, module_title: str) -> Dict:
    return record_teacher_module_view_impl(
        customer_id=int(customer_id), module_order=int(module_order), module_title=str(module_title)
    )


def get_teacher_module_views_impl(
    *,
    customer_id: int,
    limit: int = 50,
    database_path: str | None = None,
) -> List[Dict]:
    """Return recent teacher module views for a customer."""

    ensure_teacher_views_schema(database_path)

    with connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, customer_id, module_order, module_title, created_at
            FROM teacher_module_views
            WHERE customer_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (int(customer_id), int(limit)),
        ).fetchall()

    return [
        {
            "viewId": r["id"],
            "customerId": int(r["customer_id"]),
            "moduleOrder": int(r["module_order"]),
            "moduleTitle": r["module_title"],
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


@mcp.tool()
def get_teacher_module_views(customer_id: int, limit: int = 50) -> List[Dict]:
    return get_teacher_module_views_impl(customer_id=int(customer_id), limit=int(limit))


def get_last_teacher_module_impl(customer_id: int, database_path: str | None = None) -> Dict | None:
    """Return the most recently viewed module for this customer, if any."""

    views = get_teacher_module_views_impl(customer_id=int(customer_id), limit=1, database_path=database_path)
    if not views:
        return None
    return views[0]


@mcp.tool()
def get_last_teacher_module(customer_id: int) -> Dict | None:
    return get_last_teacher_module_impl(customer_id=int(customer_id))


def now_date() -> str:
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

    now = now_date()
    with connect(database_path) as conn:
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

    now = now_date()

    with connect(database_path) as conn:
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


def row_to_dict(row: sqlite3.Row | None) -> Dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}

def get_customer_info_impl(
    *,
    id: int,
    name: str,
    age: int,
    state: str,
    vehicleName: str,
    coverageType: str,
    database_path: str | None = None,
) -> Dict:
    """Implementation for creating/updating a customer profile.

    This is separated from the MCP tool wrapper so that non-MCP callers (FastAPI, tests)
    can call it as a normal Python function.
    """

    now = datetime.now(timezone.utc).strftime("%m/%d/%Y")

    path = database_path or db_path
    init_db(path)

    with sqlite3.connect(path) as conn:
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
            (int(id), str(name), int(age), str(state), str(vehicleName), str(coverageType), now, now),
        )

    return {
        "id": int(id),
        "name": str(name),
        "age": int(age),
        "state": str(state),
        "vehicleName": str(vehicleName),
        "coverageType": str(coverageType),
        "updatedAt": now,
    }


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
    
    return get_customer_info_impl(
        id=int(id),
        name=str(name),
        age=int(age),
        state=str(state),
        vehicleName=str(vehicleName),
        coverageType=str(coverageType),
    )


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

    return plan_curriculum_impl(customer_id=customer_id)


def plan_curriculum_impl(customer_id: int) -> List[Dict]:
    """Create/persist a curriculum plan for a customer.

    This is the non-MCP implementation so it can be called from FastAPI/tests
    without going through the @mcp.tool wrapper (which turns functions into
    FunctionTool objects).
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, age, state, vehicle_name, coverage_type FROM customers WHERE id = ?;",
            (customer_id,),
        ).fetchone()

    if row is None:
        raise ValueError(
            f"Customer {customer_id} not found. Call get_customer_info first to store the profile."
        )

    user_age = int(row["age"])

    curriculum = [
        "What is Car Insurance?",
        "Understanding Deductibles",
        "Steps to Take During a Car Accident",
        "Do’s and Don’ts of Safe Driving",
        "What Is a Premium?",
        "What Is a Claim?",
        "How to File a Claim",
        "What Is Coverage?",
        "Types of Coverage for Auto Insurance",
        "Factors Affecting Insurance Rates",
        "Impact of Driving History on Rates",
        "How to Maintain a Clean Driving Record",
        "Common Auto Insurance Terms Explained",
        "How to Choose the Right Insurance Plan",
        "Importance of Liability Coverage",
        "Understanding Comprehensive and Collision Coverage",
        "How to Lower Your Insurance Premiums",
        "Seasonal Driving Tips and Insurance Implications",
        "Impact of Traffic Violations on Insurance Rates",
        "How to Read Your Insurance Policy",
        "Benefits of Bundling Insurance Policies",
        "Understanding No-Fault Insurance",
        "What to Do in Case of a Total Loss",
        "How to Handle Uninsured Motorist Situations",
        "Understanding Policy Endorsements",
        "How to Dispute a Denied Claim",
        "Understanding Rental Car Coverage",
    ]
        
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


def now_date() -> str:
    return datetime.now(timezone.utc).strftime("%m/%d/%Y")


def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def keyword_score(answer: str, expected: str) -> float:
    """Very small, deterministic grader.

    Returns a score in [0, 1].
    """

    a = normalize_text(answer)
    e = normalize_text(expected)
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


def age_tone(age: int) -> str:
    return "teen" if int(age) < 18 else "adult"


def build_cards_for_module(module_title: str, module_description: str, age: int, module_order: int) -> List[Dict]:
    """Deterministic, template-based flashcards.

    This avoids requiring an LLM, but still returns useful Quizlet-style cards.
    """

    tone = age_tone(age)
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
            build_cards_for_module(
                module_title=m["module"],
                module_description=m.get("description", ""),
                age=int(m.get("customerAge", 18)),
                module_order=int(m["order"]),
            )
        )
        if len(cards) >= int(limit):
            break

    return cards[: int(limit)]


def persist_quiz_session(session_id: str, customer_id: int, module_order: int | None):
    now = now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            INSERT INTO quiz_sessions (id, customer_id, module_order, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, 'active');
            """,
            (session_id, int(customer_id), int(module_order) if module_order is not None else None, now, now),
        )


def persist_quiz_cards(session_id: str, cards: List[Dict]):
    now = now_date()
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


def get_next_card(session_id: str) -> Dict | None:
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

    persist_quiz_session(session_id=session_id, customer_id=customer_id, module_order=module_order)
    persist_quiz_cards(session_id=session_id, cards=cards)

    next_card = get_next_card(session_id)
    return {"sessionId": session_id, "card": next_card, "totalCards": len(cards)}


@mcp.tool()
def get_next_flashcard(session_id: str) -> Dict:
    return get_next_flashcard_impl(session_id=session_id)


def get_next_flashcard_impl(session_id: str) -> Dict:
    """Get the next due/new flashcard (without revealing the back)."""

    card = get_next_card(session_id)
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
        score = keyword_score(answer, expected)
        correct = bool(score >= 0.6)
        now = now_date()

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

    next_card = get_next_card(session_id)
    return {
        "sessionId": session_id,
        "cardId": card_id,
        "correct": correct,
        "score": score,
        "expected": expected,
        "feedback": "Nice!" if correct else "Not quite",
        "nextCard": next_card,
        "done": next_card is None,
    }

def knowledge_question_weight(q_type: str) -> float:
    """Scoring weights requested by user.

    - multiple_choice: 1.0
    - true_false: 0.5
    """

    t = (q_type or "").strip().lower()
    if t in {"tf", "truefalse", "true_false", "true/false"}:
        return 0.5
    return 1.0


def _slugify_topic(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[^a-z0-9\s_-]", "", t)
    t = re.sub(r"[\s_-]+", "_", t).strip("_")
    return t or "general"


def _seed_token(text: str) -> str:
    """Stable seed token for embedding inside question ids.

    Important: must not contain underscores because question ids are underscore-delimited.
    """

    raw = (text or "").strip()
    if not raw:
        return "default"
    tok = re.sub(r"[^a-zA-Z0-9]", "", raw)
    tok = tok[:32]
    return tok or "default"


def _topic_for_module(module_title: str, module_description: str) -> str:
    """Deterministic mapping from module text -> topic key.

    This is shared by both the legacy static bank and the new generator.
    """

    title_l = (module_title or "").lower()
    title_norm = title_l.replace("’", "'").strip()
    title_map = {
        "what is car insurance?": "car_insurance_basics",
        "understanding deductibles": "deductibles_full",
        "what is a premium?": "premium_basics",
        "steps to take during a car accident": "accident_steps",
        "do's and don'ts of safe driving": "safe_driving",
        "filing a claim after an accident": "claim_after_accident",
        "types of car insurance coverage": "coverage_types",
        "liability insurance": "liability",
        "collision coverage": "collision",
        "comprehensive coverage": "comprehensive",
        "medical payments / pip": "medical_payments",
        "uninsured / underinsured motorist coverage": "uninsured_underinsured",
        "gap insurance": "gap_insurance",
        "rental car coverage": "rental_car",
        "deductibles": "deductibles_short",
        "premiums": "premiums_short",
        "insurance claims": "claims_short",
        "insurance adjusters": "adjusters",
        "insurance policy": "policy",
        "coverage limits": "coverage_limits",
        "policy renewal and cancellation": "policy_renewal",
        "state insurance requirements": "state_requirements",
        "factors affecting insurance rates": "rate_factors_short",
        "driving record impact": "driving_record_impact",
        "discounts": "discounts_short",
        "avoiding insurance fraud": "fraud",
        "responsible driving and insurance": "responsible_driving",
    }
    if title_norm in title_map:
        return title_map[title_norm]
    desc_l = (module_description or "").lower()
    combined = f"{title_l} {desc_l}".strip()

    topic_keywords: list[tuple[str, list[str]]] = [
        ("car_insurance_basics", ["what is car insurance"]),
        ("deductible", ["understanding deductibles", "deductible", "deductibles", "deduct"]),
        ("premium", ["what is a premium", "premium", "premiums", "grace period"]),
        ("claim_filing", ["how to file a claim", "file a claim"]),
    ("claim", ["what is a claim", "claim", "claims process", "claims"]),
    ("rental_car", ["rental car", "rental coverage"]),
    ("roadside", ["roadside assistance", "roadside assistance coverage"]),
    ("coverage_types", ["types of coverage for auto insurance", "types of coverage"]),
    ("coverage", ["what is coverage", "coverage", "coverages", "state minimum"]),
        ("liability", ["liability coverage", "liability"]),
        (
            "comp_collision",
            [
                "comprehensive and collision",
                "comprehensive coverage",
                "collision coverage",
            ],
        ),
        ("choose_plan", ["choose the right insurance plan", "choose the right", "choose a plan", "insurance plan"]),
        ("terms", ["common auto insurance terms", "terms explained", "auto insurance terms"]),
        ("lower_premium", ["how to lower your insurance premiums", "lower your insurance premiums", "lower your premiums"]),
        ("bundling", ["bundling", "bundle policies", "bundling insurance"]),
        ("no_fault", ["no-fault", "no fault"]),
        (
            "policy_interpretation",
            ["read your insurance policy", "insurance policy", "policy interpretation", "declarations", "endorsement"],
        ),
        ("endorsements", ["policy endorsements", "endorsement"]),
    ("dispute", ["dispute a denied claim", "denied claim", "appeal a claim"]),
        ("uninsured_motorist", ["uninsured motorist"]),
        ("total_loss", ["total loss"]),
        ("accident_steps", ["steps to take", "car accident", " accident", " crash"]),
        ("seasonal", ["seasonal driving", "winter driving", "summer driving"]),
        ("clean_record", ["clean driving record", "maintain a clean driving record"]),
        ("driving_history", ["driving history"]),
        ("violations", ["traffic violations", "violations", "tickets", "speeding"]),
        (
            "rate_factors",
            [
                "factors affecting insurance rates",
                "insurance rates",
                "rates",
                "credit score",
                "telematics",
                "location",
                "mileage",
            ],
        ),
        ("safe_driving", ["safe driving", "do's and don'ts", "defensive driving", "driving tips"]),
    ("discounts", ["discount", "discounts"]),
        ("gap", ["gap insurance"]),
        ("fraud", ["insurance fraud", " fraud"]),
        ("vehicle_mods", ["vehicle modifications"]),
        ("maintenance", ["vehicle maintenance"]),
        ("switch_provider", ["switch insurance", "switch providers"]),
        ("commercial_vs_personal", ["commercial auto", "personal and commercial"]),
        ("multi_vehicle", ["multiple vehicles"]),
        (
            "young_driver",
            ["first-time drivers", "young drivers", "student drivers", "safe driving courses"],
        ),
    ]

    for t, kws in topic_keywords:
        for kw in kws:
            if kw and kw in combined:
                return t
    return "general"


def generate_topic_aligned_questions(
    *,
    module_order: int,
    module_title: str,
    module_description: str,
    count: int = 10,
    seed: str | None = None,
) -> List[Dict]:
    """Generate *new* deterministic questions aligned to the detected topic.

    This function is intentionally **LLM-free** and deterministic.

    Contract:
    - Returns `count` questions (default 10).
    - Ids are unique per (module_order, seed) so quiz attempts can safely re-fetch.
    - For known curricula topics, returns the **exact** fixed question text/choices
      (verbatim) used by the frontend Knowledge Quiz.
    """

    mo = int(module_order)
    topic = _topic_for_module(module_title, module_description)
    topic_token = _slugify_topic(topic).replace("_", "") or "general"

    seed_str = seed or now_date()
    seed_slug = _seed_token(seed_str)

    def qid(kind: str, i: int) -> str:
        return f"kv2_m{mo}_{topic_token}_{seed_slug}_{kind}{i}"  

    def mc(i: int, prompt: str, choices: List[str], correct_index: int, explanation: str) -> Dict:
        return {
            "id": qid("mc", i),
            "moduleOrder": mo,
            "topic": topic,
            "type": "multiple_choice",
            "prompt": prompt,
            "choices": choices,
            "correctIndex": int(correct_index),
            "expected": choices[int(correct_index)],
            "explanation": explanation,
            "weight": 1.0,
        }

    def tf(i: int, prompt: str, correct: bool, explanation: str) -> Dict:
        return {
            "id": qid("tf", i),
            "moduleOrder": mo,
            "topic": topic,
            "type": "true_false",
            # NOTE: prompt is passed in verbatim because we must not deviate.
            "prompt": prompt,
            "choices": ["True", "False"],
            "correctIndex": 0 if bool(correct) else 1,
            "expected": "True" if bool(correct) else "False",
            "explanation": explanation,
            "weight": 0.5,
        }

    def _explanation_generic() -> str:
        # Keep explanations short and stable; UI doesn't require them.
        return "Answer is based on standard auto insurance concepts."

    def _mc10(
        prompts_and_choices: List[tuple[str, List[str], int]],
        tf_prompts_and_truth: List[tuple[str, bool]],
    ) -> List[Dict]:
        out: List[Dict] = []
        mc_i = 0
        for p, choices, idx in prompts_and_choices:
            mc_i += 1
            out.append(mc(mc_i, p, choices, idx, _explanation_generic()))
        tf_i = mc_i
        for p, truth in tf_prompts_and_truth:
            tf_i += 1
            out.append(tf(tf_i, p, truth, _explanation_generic()))
        # Ensure ordering is exactly MC first then TF (matches provided layout).
        return out

    def _ordered(defs: List[Dict]) -> List[Dict]:
        out: List[Dict] = []
        i = 0
        for d in defs:
            i += 1
            if d.get("type") == "mc":
                out.append(mc(i, d["prompt"], d["choices"], d["correct"], _explanation_generic()))
            else:
                out.append(tf(i, d["prompt"], d["correct"], _explanation_generic()))
        return out

    # Exact, fixed question banks (verbatim) keyed by detected topic.
    EXACT_BANKS: dict[str, List[Dict]] = {
        "car_insurance_basics": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is the primary purpose of car insurance?",
                    "choices": [
                        "Improve driving skills",
                        "Protect drivers financially after accidents or losses",
                        "Reduce fuel costs",
                        "Increase resale value",
                    ],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Which best describes car insurance?",
                    "choices": ["Savings account", "Legal contract", "Driving permit", "Warranty"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What does liability insurance cover?",
                    "choices": [
                        "Your car",
                        "Injuries and damages you cause to others",
                        "Maintenance",
                        "Theft",
                    ],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Why is car insurance required in most states?",
                    "choices": [
                        "Ensure cars are new",
                        "Reduce traffic",
                        "Ensure drivers can pay for damages",
                        "Track habits",
                    ],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Who pays the premium?",
                    "choices": ["Insurer", "Government", "Manufacturer", "Policyholder"],
                    "correct": 3,
                },
                {
                    "type": "mc",
                    "prompt": "Which factor affects insurance cost?",
                    "choices": ["Favorite color", "Driving history", "Shoe size", "Phone brand"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What happens if you stop paying premiums?",
                    "choices": ["Coverage increases", "Policy canceled", "Free repairs", "Nothing"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Car insurance helps cover financial losses.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Insurance only covers your own vehicle.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Insurance protects against large unexpected expenses.",
                    "correct": True,
                },
            ]
        ),
        "deductibles_full": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is a deductible?",
                    "choices": [
                        "Monthly payment",
                        "Amount you pay before insurance covers costs",
                        "Fee",
                        "Interest",
                    ],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When do you pay a deductible?",
                    "choices": ["Buying insurance", "Filing a claim", "Before driving", "Monthly"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Higher deductible usually means:",
                    "choices": ["Higher premium", "Lower premium", "No coverage", "Free repairs"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "$500 deductible, $2,000 repair — insurance pays:",
                    "choices": ["$500", "$1,500", "$2,000", "$0"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Deductibles usually apply to:",
                    "choices": ["Liability", "Collision", "Medical", "Roadside"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Who chooses deductible amount?",
                    "choices": ["Government", "Insurer", "Policyholder", "Mechanic"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Deductibles help prevent:",
                    "choices": ["Accidents", "Fraud/small claims", "Rate increases", "Cancellation"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Deductibles are paid out of pocket.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Liability coverage usually has a deductible.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Higher deductibles can lower premiums.",
                    "correct": True,
                },
            ]
        ),
        "accident_steps": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "First thing to check after accident?",
                    "choices": ["Phone", "Injuries", "Policy", "Damage"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Who to call if injuries occur?",
                    "choices": ["Agent", "Tow truck", "Emergency services", "Mechanic"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "What info should be exchanged?",
                    "choices": ["Social media", "Insurance/contact info", "Salary", "Driving record"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Why take photos?",
                    "choices": ["Social media", "Document damage", "DIY estimate", "Avoid police"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When contact police?",
                    "choices": ["Never", "Minor accidents", "Injuries/major damage", "Only asked"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "What should you avoid admitting?",
                    "choices": ["Name", "Fault", "Provider", "License"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When notify insurer?",
                    "choices": ["ASAP", "After repair", "After court", "Never"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Leaving scene is allowed if damage is minor.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Photos support claims.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Staying calm is important.",
                    "correct": True,
                },
            ]
        ),
        "safe_driving": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Safe driving habit?",
                    "choices": ["Speeding", "Seat belts", "Texting", "Tailgating"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What should NOT be done?",
                    "choices": ["Focus", "Use mirrors", "Text", "Signal"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Defensive driving means:",
                    "choices": ["Aggressive", "Anticipating hazards", "Slow always", "Ignore others"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Biggest accident risk?",
                    "choices": ["Awareness", "Distracted driving", "Obeying laws", "Signals"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Safe distance prevents:",
                    "choices": ["Tickets", "Rear-end collisions", "Flats", "Theft"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When use headlights?",
                    "choices": ["Night only", "Low visibility", "Tunnels", "Never"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Road rage is:",
                    "choices": ["Safe", "Encouraged", "Dangerous", "Legal"],
                    "correct": 2,
                },
                {
                    "type": "tf",
                    "prompt": "Speed limits optional.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Defensive driving reduces risk.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Safe driving can lower insurance costs.",
                    "correct": True,
                },
            ]
        ),
        "premium_basics": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Premium is:",
                    "choices": ["Repair cost", "Insurance payment", "Deductible", "Fine"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Premiums are paid:",
                    "choices": ["Once", "Monthly/annually", "After accidents", "Never"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Who pays premium?",
                    "choices": ["Insurer", "Government", "Policyholder", "Mechanic"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Premium cost depends on:",
                    "choices": ["Driving history", "Shoe size", "Color", "Weather"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Missing payments can cause:",
                    "choices": ["Discounts", "Cancellation", "Free coverage", "Refund"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Premiums lower for:",
                    "choices": ["Risky drivers", "Safe drivers", "New drivers", "Uninsured"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Premiums help insurers:",
                    "choices": ["Pay claims", "Ticket drivers", "Fix roads", "Sell cars"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Premiums refunded after accidents.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Premiums vary by driver.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Premiums required to keep coverage.",
                    "correct": True,
                },
            ]
        ),
        "coverage_types": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Which type of insurance is required in most states?",
                    "choices": ["Collision", "Comprehensive", "Liability", "Gap"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Which coverage pays for damage to your car after an accident?",
                    "choices": ["Liability", "Collision", "Medical Payments", "Rental"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Which coverage protects against theft or vandalism?",
                    "choices": ["Collision", "Liability", "Comprehensive", "Uninsured Motorist"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "What does uninsured motorist coverage protect against?",
                    "choices": ["Weather damage", "Mechanical failure", "Drivers without insurance", "Your deductible"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Which coverage helps pay medical bills regardless of fault?",
                    "choices": ["Liability", "Medical Payments / PIP", "Collision", "Gap"],
                    "correct": 1,
                },
            ]
        ),
        "liability": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What does bodily injury liability cover?",
                    "choices": ["Your injuries", "Injuries to others", "Vehicle repairs", "Theft"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Property damage liability covers damage to what?",
                    "choices": ["Your car", "Your home", "Other people’s property", "Medical bills"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Who does liability insurance protect?",
                    "choices": ["Passengers", "Other drivers", "You as the driver", "Mechanics"],
                    "correct": 2,
                },
                {
                    "type": "mc",
                    "prompt": "Is liability insurance required by law in most states?",
                    "choices": ["Yes", "No"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Liability insurance pays for your own car repairs.",
                    "correct": False,
                },
            ]
        ),
        "collision": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Collision coverage applies when you hit what?",
                    "choices": ["Another vehicle or object", "A medical bill", "Theft", "Weather"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Does collision cover hit-and-run accidents?",
                    "choices": ["Yes", "No"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Is collision coverage required by law?",
                    "choices": ["Yes", "No"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Who usually requires collision coverage?",
                    "choices": ["State government", "Lenders/leasing companies", "Police", "Mechanics"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Collision coverage includes a deductible.",
                    "correct": True,
                },
            ]
        ),
        "comprehensive": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What type of damage does comprehensive cover?",
                    "choices": ["Accidents only", "Non-collision events", "Medical bills", "Traffic tickets"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Which is covered by comprehensive insurance?",
                    "choices": ["Car accident", "Theft", "Speeding ticket", "Oil change"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Does comprehensive cover natural disasters?",
                    "choices": ["Yes", "No"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Comprehensive insurance requires a deductible.",
                    "correct": True,
                },
                {
                    "type": "mc",
                    "prompt": "Is comprehensive mandatory in all states?",
                    "choices": ["Yes", "No"],
                    "correct": 1,
                },
            ]
        ),
        "deductibles_short": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is a deductible?",
                    "choices": ["Monthly bill", "Amount you pay before insurance", "Coverage limit", "Refund"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "A higher deductible usually means what?",
                    "choices": ["Higher premium", "Lower premium", "No coverage", "Free repairs"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When do you pay a deductible?",
                    "choices": ["Every month", "At renewal", "When filing a claim", "When buying a car"],
                    "correct": 2,
                },
                {
                    "type": "tf",
                    "prompt": "Deductibles apply to liability coverage.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Choosing a deductible affects premium cost.",
                    "correct": True,
                },
            ]
        ),
        "premiums_short": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is an insurance premium?",
                    "choices": ["Claim payout", "Monthly or annual cost", "Deductible", "Discount"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Which factor affects premium cost?",
                    "choices": ["Driving record", "Eye color", "Shoe size", "Favorite food"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Safer drivers usually pay what?",
                    "choices": ["Higher premiums", "Lower premiums", "No premiums", "Same premiums"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Premiums are paid to whom?",
                    "choices": ["Police", "Insurance company", "DMV", "Repair shop"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Premiums can be paid monthly or annually.",
                    "correct": True,
                },
            ]
        ),
        "claims_short": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is an insurance claim?",
                    "choices": ["Policy document", "Request for payment", "Traffic citation", "Bill"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When should you file a claim?",
                    "choices": ["After an accident", "Before driving", "Every month", "At renewal"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Who investigates a claim?",
                    "choices": ["Judge", "Insurance adjuster", "Police officer", "Mechanic"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Claims can affect future premiums.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "False claims are legal.",
                    "correct": False,
                },
            ]
        ),
        "policy": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is an insurance policy?",
                    "choices": ["Receipt", "Legal contract", "Claim form", "License"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What does a policy outline?",
                    "choices": ["Coverage and limits", "Driving routes", "Gas prices", "Repair shops"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Policies include coverage limits.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Policies can be canceled for nonpayment.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Policy terms are negotiable after signing.",
                    "correct": False,
                },
            ]
        ),
        "coverage_limits": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is a coverage limit?",
                    "choices": ["Minimum premium", "Maximum payout", "Deductible", "Discount"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What happens if damages exceed limits?",
                    "choices": ["Insurance pays all", "You pay the rest", "Claim denied", "No effect"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Higher limits usually mean what?",
                    "choices": ["Lower cost", "Higher premium", "No coverage", "Same price"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Coverage limits apply to liability insurance.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Limits protect against large financial loss.",
                    "correct": True,
                },
            ]
        ),
        "discounts_short": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Which can qualify you for a discount?",
                    "choices": ["Safe driving", "Speeding tickets", "Late payments", "Claims"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Bundling policies can reduce premiums.",
                    "correct": True,
                },
                {
                    "type": "mc",
                    "prompt": "Student discounts are based on what?",
                    "choices": ["GPA", "Age", "Income", "Vehicle size"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Discounts are automatic.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Anti-theft devices may reduce premiums.",
                    "correct": True,
                },
            ]
        ),
        "driving_record_impact": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What affects your insurance rate most?",
                    "choices": ["Driving history", "Music taste", "Phone brand", "Weather"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Accidents can cause premiums to do what?",
                    "choices": ["Decrease", "Increase", "Disappear", "Stay the same"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Tickets remain on record for several years.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "A clean record leads to lower premiums.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Insurance companies ignore driving history.",
                    "correct": False,
                },
            ]
        ),
        "claim_after_accident": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is the first thing you should do after an accident?",
                    "choices": [
                        "Leave the scene",
                        "Ensure safety and call for help",
                        "Call your insurance immediately",
                        "Fix the car",
                    ],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When should you contact your insurance company?",
                    "choices": ["Weeks later", "Immediately or soon after", "Only if forced", "Never"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What information is helpful when filing a claim?",
                    "choices": ["Photos and police report", "Social media posts", "Opinions", "Repair estimates only"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Fault must be admitted at the scene.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Claims should be reported honestly.",
                    "correct": True,
                },
            ]
        ),
        "adjusters": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is an insurance adjuster?",
                    "choices": ["Lawyer", "Investigator of claims", "Mechanic", "Agent"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "What does an adjuster determine?",
                    "choices": ["Fault and payout", "Ticket fines", "Vehicle price", "Insurance laws"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Adjusters work for whom?",
                    "choices": ["DMV", "Insurance company", "Police", "Court"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Adjusters inspect vehicle damage.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Adjusters decide insurance premiums.",
                    "correct": False,
                },
            ]
        ),
        "rental_car": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What does rental car coverage provide?",
                    "choices": ["Gas", "Temporary vehicle", "Repairs", "Insurance discount"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When is rental coverage used?",
                    "choices": ["After an accident", "During oil changes", "When selling a car", "When renewing policy"],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Is rental coverage mandatory?",
                    "choices": ["Yes", "No"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Rental coverage has daily limits.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Rental coverage replaces collision insurance.",
                    "correct": False,
                },
            ]
        ),
        "medical_payments": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What does Medical Payments coverage pay for?",
                    "choices": ["Car repairs", "Medical expenses", "Property damage", "Tickets"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "PIP stands for what?",
                    "choices": [
                        "Personal Injury Protection",
                        "Payment Insurance Plan",
                        "Premium Increase Program",
                        "Property Insurance Policy",
                    ],
                    "correct": 0,
                },
                {
                    "type": "mc",
                    "prompt": "Does PIP cover passengers?",
                    "choices": ["Yes", "No"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "PIP applies regardless of fault.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "PIP is required in some states.",
                    "correct": True,
                },
            ]
        ),
        "uninsured_underinsured": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What does uninsured motorist coverage protect against?",
                    "choices": ["Theft", "Drivers without insurance", "Weather damage", "Repairs"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Underinsured motorist coverage applies when?",
                    "choices": [
                        "Other driver has no insurance",
                        "Other driver lacks enough coverage",
                        "You are uninsured",
                        "You are at fault",
                    ],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "This coverage protects you and passengers.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "It covers vehicle damage and injuries.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "This coverage is required in all states.",
                    "correct": False,
                },
            ]
        ),
        "gap_insurance": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is gap insurance?",
                    "choices": ["Covers repair gaps", "Pays difference between loan and value", "Covers rental cars", "Covers tickets"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Who benefits most from gap insurance?",
                    "choices": ["Owners of older cars", "Leased or financed vehicle owners", "Pedestrians", "Mechanics"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "When is gap insurance useful?",
                    "choices": ["Theft or total loss", "Oil change", "Flat tire", "Maintenance"],
                    "correct": 0,
                },
                {
                    "type": "tf",
                    "prompt": "Gap insurance is mandatory.",
                    "correct": False,
                },
                {
                    "type": "tf",
                    "prompt": "Gap insurance pays your deductible.",
                    "correct": False,
                },
            ]
        ),
        "policy_renewal": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is policy renewal?",
                    "choices": ["Ending coverage", "Continuing coverage", "Filing a claim", "Buying a car"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Policies usually renew how often?",
                    "choices": ["Monthly", "Every 6 or 12 months", "Daily", "Never"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Nonpayment can result in what?",
                    "choices": ["Discount", "Cancellation", "Refund", "Bonus"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Insurers must notify before cancellation.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "You can change insurers at renewal.",
                    "correct": True,
                },
            ]
        ),
        "state_requirements": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Who sets minimum insurance requirements?",
                    "choices": ["Federal government", "State government", "Insurance companies", "Police"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Most states require what coverage?",
                    "choices": ["Collision", "Liability", "Comprehensive", "Gap"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Driving uninsured can lead to what?",
                    "choices": ["Discounts", "Fines or license suspension", "Free insurance", "Lower premiums"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Requirements vary by state.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Insurance laws never change.",
                    "correct": False,
                },
            ]
        ),
        "rate_factors_short": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What affects insurance rates?",
                    "choices": ["Driving record", "Location", "Vehicle type", "All of the above"],
                    "correct": 3,
                },
                {
                    "type": "mc",
                    "prompt": "Younger drivers usually pay what?",
                    "choices": ["Less", "More"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Sports cars usually cost more to insure.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Credit history can affect rates in some states.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Rates are the same for everyone.",
                    "correct": False,
                },
            ]
        ),
        "fraud": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "What is insurance fraud?",
                    "choices": ["Honest mistake", "Lying for benefits", "Filing claims", "Paying premiums"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Which is an example of fraud?",
                    "choices": ["Reporting a real accident", "Exaggerating damages", "Paying deductible", "Buying insurance"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Fraud can lead to legal penalties.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Fraud affects premiums for everyone.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Fraud is harmless.",
                    "correct": False,
                },
            ]
        ),
        "responsible_driving": _ordered(
            [
                {
                    "type": "mc",
                    "prompt": "Responsible driving helps do what?",
                    "choices": ["Increase premiums", "Lower insurance costs", "Cancel policies", "Avoid coverage"],
                    "correct": 1,
                },
                {
                    "type": "mc",
                    "prompt": "Defensive driving courses can provide what?",
                    "choices": ["Tickets", "Discounts", "Fines", "Claims"],
                    "correct": 1,
                },
                {
                    "type": "tf",
                    "prompt": "Following traffic laws reduces accidents.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Safe drivers are considered lower risk.",
                    "correct": True,
                },
                {
                    "type": "tf",
                    "prompt": "Insurance encourages responsible driving.",
                    "correct": True,
                },
            ]
        ),
    }

    topic_aliases = {
        "deductible": "deductibles_full",
        "premium": "premium_basics",
        "claim": "claims_short",
        "claim_filing": "claim_after_accident",
        "coverage": "coverage_limits",
        "coverage_types": "coverage_types",
        "liability": "liability",
        "comp_collision": "collision",
        "choose_plan": "policy",
        "terms": "policy",
        "lower_premium": "discounts_short",
        "bundling": "discounts_short",
        "no_fault": "policy",
        "policy_interpretation": "policy",
        "endorsements": "policy",
        "dispute": "claims_short",
        "uninsured_motorist": "uninsured_underinsured",
        "total_loss": "gap_insurance",
        "seasonal": "responsible_driving",
        "clean_record": "responsible_driving",
        "driving_history": "driving_record_impact",
        "violations": "driving_record_impact",
        "rate_factors": "rate_factors_short",
    }

    exact = EXACT_BANKS.get(topic) or EXACT_BANKS.get(topic_aliases.get(topic, ""))
    if exact:
        # Respect requested `count` (default 10).
        # If the exact bank is shorter than `count` (some topics only define 5),
        # repeat deterministically so callers always get `count` items.
        if count <= 0:
            return []
        if len(exact) >= int(count):
            return exact[: int(count)]
        if not exact:
            return []
        out: List[Dict] = []
        i = 0
        while len(out) < int(count):
            out.append(exact[i % len(exact)])
            i += 1
        return out

    # Fallback: keep prior behavior (generate deterministic, generic questions)
    # for topics that don't have an exact question bank yet.
    templates: dict[str, list[Dict]] = {
        "choose_plan": [
            mc(
                1,
                "When choosing an insurance plan, what should you compare?",
                [
                    "Coverage limits + deductibles + premium cost",
                    "Only the logo",
                    "Only how fast it loads",
                    "Only the color of your insurance card",
                ],
                0,
                "Comparing coverage, limits, and cost helps you pick an appropriate plan.",
            ),
            tf(
                1,
                "True/False: The cheapest policy is always the best policy.",
                False,
                "Cheapest can mean less protection or more exclusions.",
            ),
        ],
    }

    bank = templates.get(topic) or templates.get("choose_plan")
    if not bank:
        return []
    if count <= 0:
        return []
    if len(bank) >= int(count):
        return bank[: int(count)]
    out: List[Dict] = []
    i = 0
    while len(out) < int(count):
        out.append(bank[i % len(bank)])
        i += 1
    return out
def knowledge_bank_for_module(module_title: str, module_description: str, module_order: int) -> List[Dict]:
    """Deterministic question bank for a single curriculum module.

    Returns 10 questions per module (mixed multiple-choice and true/false).
    This is intentionally LLM-free so tests are stable.
    """

    def qid(suffix: str) -> str:
        return f"kv_m{int(module_order)}_{suffix}"

    topic = _topic_for_module(module_title, module_description)

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

    def tf(suffix: str, prompt: str, correct: bool, explanation: str) -> Dict:
        return {
            "id": qid(suffix),
            "moduleOrder": int(module_order),
            "topic": topic,
            "type": "true_false",
            "prompt": prompt,
            "choices": ["True", "False"],
            "correctIndex": 0 if bool(correct) else 1,
            "expected": "True" if bool(correct) else "False",
            "explanation": explanation,
            "weight": 0.5,
        }

    def mc_q(suffix: str, prompt: str, choices: List[str], correct_index: int) -> Dict:
        return mc(suffix, prompt, choices, correct_index, "")

    def tf_q(suffix: str, prompt: str, correct: bool) -> Dict:
        return tf(suffix, prompt, correct, "")

    bank_by_title: Dict[str, List[Dict]] = {
        "what_is_car_insurance": [
            mc_q(
                "mc1",
                "What is the primary purpose of car insurance?",
                [
                    "Improve driving skills",
                    "Protect drivers financially after accidents or losses",
                    "Reduce fuel costs",
                    "Increase resale value",
                ],
                1,
            ),
            mc_q(
                "mc2",
                "Which best describes car insurance?",
                [
                    "Savings account",
                    "Legal contract",
                    "Driving permit",
                    "Warranty",
                ],
                1,
            ),
            mc_q(
                "mc3",
                "What does liability insurance cover?",
                [
                    "Your car",
                    "Injuries and damages you cause to others",
                    "Maintenance",
                    "Theft",
                ],
                1,
            ),
            mc_q(
                "mc4",
                "Why is car insurance required in most states?",
                [
                    "Ensure cars are new",
                    "Reduce traffic",
                    "Ensure drivers can pay for damages",
                    "Track habits",
                ],
                2,
            ),
            mc_q(
                "mc5",
                "Who pays the premium?",
                [
                    "Insurer",
                    "Government",
                    "Manufacturer",
                    "Policyholder",
                ],
                3,
            ),
            mc_q(
                "mc6",
                "Which factor affects insurance cost?",
                ["Favorite color", "Driving history", "Shoe size", "Phone brand"],
                1,
            ),
            mc_q(
                "mc7",
                "What happens if you stop paying premiums?",
                [
                    "Coverage increases",
                    "Policy canceled",
                    "Free repairs",
                    "Nothing",
                ],
                1,
            ),
            tf_q(
                "tf8",
                "Car insurance helps cover financial losses.",
                True,
            ),
            tf_q(
                "tf9",
                "Insurance only covers your own vehicle.",
                False,
            ),
            tf_q(
                "tf10",
                "Insurance protects against large unexpected expenses.",
                True,
            ),
        ],
        "understanding_deductibles": [
            mc_q(
                "mc1",
                "What is a deductible?",
                [
                    "Monthly payment",
                    "Amount you pay before insurance covers costs",
                    "Fee",
                    "Interest",
                ],
                1,
            ),
            mc_q(
                "mc2",
                "When do you pay a deductible?",
                ["Buying insurance", "Filing a claim", "Before driving", "Monthly"],
                1,
            ),
            mc_q(
                "mc3",
                "Higher deductible usually means:",
                ["Higher premium", "Lower premium", "No coverage", "Free repairs"],
                1,
            ),
            mc_q(
                "mc4",
                "$500 deductible, $2,000 repair — insurance pays:",
                ["$500", "$1,500", "$2,000", "$0"],
                1,
            ),
            mc_q(
                "mc5",
                "Deductibles usually apply to:",
                ["Liability", "Collision", "Medical", "Roadside"],
                1,
            ),
            mc_q(
                "mc6",
                "Who chooses deductible amount?",
                ["Government", "Insurer", "Policyholder", "Mechanic"],
                2,
            ),
            mc_q(
                "mc7",
                "Deductibles help prevent:",
                [
                    "Accidents",
                    "Fraud/small claims",
                    "Rate increases",
                    "Cancellation",
                ],
                1,
            ),
            tf_q("tf8", "Deductibles are paid out of pocket.", True),
            tf_q("tf9", "Liability coverage usually has a deductible.", False),
            tf_q("tf10", "Higher deductibles can lower premiums.", True),
        ],
        "steps_to_take_during_a_car_accident": [
            mc_q(
                "mc1",
                "First thing to check after accident?",
                ["Phone", "Injuries", "Policy", "Damage"],
                1,
            ),
            mc_q(
                "mc2",
                "Who to call if injuries occur?",
                ["Agent", "Tow truck", "Emergency services", "Mechanic"],
                2,
            ),
            mc_q(
                "mc3",
                "What info should be exchanged?",
                ["Social media", "Insurance/contact info", "Salary", "Driving record"],
                1,
            ),
            mc_q(
                "mc4",
                "Why take photos?",
                ["Social media", "Document damage", "DIY estimate", "Avoid police"],
                1,
            ),
            mc_q(
                "mc5",
                "When contact police?",
                ["Never", "Minor accidents", "Injuries/major damage", "Only asked"],
                2,
            ),
            mc_q(
                "mc6",
                "What should you avoid admitting?",
                ["Name", "Fault", "Provider", "License"],
                1,
            ),
            mc_q(
                "mc7",
                "When notify insurer?",
                ["ASAP", "After repair", "After court", "Never"],
                0,
            ),
            tf_q("tf8", "Leaving scene is allowed if damage is minor.", False),
            tf_q("tf9", "Photos support claims.", True),
            tf_q("tf10", "Staying calm is important.", True),
        ],
        "dos_and_donts_of_safe_driving": [
            mc_q(
                "mc1",
                "Safe driving habit?",
                ["Speeding", "Seat belts", "Texting", "Tailgating"],
                1,
            ),
            mc_q(
                "mc2",
                "What should NOT be done?",
                ["Focus", "Use mirrors", "Text", "Signal"],
                2,
            ),
            mc_q(
                "mc3",
                "Defensive driving means:",
                ["Aggressive", "Anticipating hazards", "Slow always", "Ignore others"],
                1,
            ),
            mc_q(
                "mc4",
                "Biggest accident risk?",
                ["Awareness", "Distracted driving", "Obeying laws", "Signals"],
                1,
            ),
            mc_q(
                "mc5",
                "Safe distance prevents:",
                ["Tickets", "Rear-end collisions", "Flats", "Theft"],
                1,
            ),
            mc_q(
                "mc6",
                "When use headlights?",
                ["Night only", "Low visibility", "Tunnels", "Never"],
                1,
            ),
            mc_q("mc7", "Road rage is:", ["Safe", "Encouraged", "Dangerous", "Legal"], 2),
            tf_q("tf8", "Speed limits optional.", False),
            tf_q("tf9", "Defensive driving reduces risk.", True),
            tf_q("tf10", "Safe driving can lower insurance costs.", True),
        ],
        "what_is_a_premium": [
            mc_q("mc1", "Premium is:", ["Repair cost", "Insurance payment", "Deductible", "Fine"], 1),
            mc_q(
                "mc2",
                "Premiums are paid:",
                ["Once", "Monthly/annually", "After accidents", "Never"],
                1,
            ),
            mc_q(
                "mc3",
                "Who pays premium?",
                ["Insurer", "Government", "Policyholder", "Mechanic"],
                2,
            ),
            mc_q(
                "mc4",
                "Premium cost depends on:",
                ["Driving history", "Shoe size", "Color", "Weather"],
                0,
            ),
            mc_q(
                "mc5",
                "Missing payments can cause:",
                ["Discounts", "Cancellation", "Free coverage", "Refund"],
                1,
            ),
            mc_q(
                "mc6",
                "Premiums lower for:",
                ["Risky drivers", "Safe drivers", "New drivers", "Uninsured"],
                1,
            ),
            mc_q("mc7", "Premiums help insurers:", ["Pay claims", "Ticket drivers", "Fix roads", "Sell cars"], 0),
            tf_q("tf8", "Premiums refunded after accidents.", False),
            tf_q("tf9", "Premiums vary by driver.", True),
            tf_q("tf10", "Premiums required to keep coverage.", True),
        ],
        "what_is_a_claim": [
            mc_q(
                "mc1",
                "A claim is:",
                ["A monthly bill", "A request for payment from insurance", "A deductible", "A discount"],
                1,
            ),
            mc_q(
                "mc2",
                "When do you file a claim?",
                ["Before driving", "After a covered loss", "When buying insurance", "Every month"],
                1,
            ),
            mc_q(
                "mc3",
                "Who reviews a claim?",
                ["Police", "Mechanic", "Insurance company", "DMV"],
                2,
            ),
            mc_q(
                "mc4",
                "Claims are filed to receive:",
                ["Tickets", "Compensation", "Premium increases", "Warnings"],
                1,
            ),
            mc_q(
                "mc5",
                "What can trigger a claim?",
                ["Accident", "Theft", "Damage", "All of the above"],
                3,
            ),
            mc_q(
                "mc6",
                "Filing many claims may:",
                ["Lower premiums", "Raise premiums", "Cancel license", "Fix credit"],
                1,
            ),
            mc_q("mc7", "Claims require:", ["Documentation", "Guessing", "No evidence", "Court approval"], 0),
            tf_q("tf8", "A claim guarantees payment.", False),
            tf_q("tf9", "Claims must be approved.", True),
            tf_q("tf10", "Claims can affect rates.", True),
        ],
        "how_to_file_a_claim": [
            mc_q(
                "mc1",
                "First step when filing a claim:",
                ["Repair car", "Contact insurer", "Pay deductible", "Call lawyer"],
                1,
            ),
            mc_q(
                "mc2",
                "Claims can be filed:",
                ["Online", "By phone", "Through an app", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "What info is needed?",
                ["Accident details", "Photos", "Police report", "All of the above"],
                3,
            ),
            mc_q(
                "mc4",
                "Who may inspect damage?",
                ["Police", "Adjuster", "DMV", "Judge"],
                1,
            ),
            mc_q(
                "mc5",
                "Filing quickly helps:",
                ["Approval speed", "Premium increase", "Denial", "Ticket dismissal"],
                0,
            ),
            mc_q("mc6", "Claims must be:", ["Honest", "Exaggerated", "Hidden", "Anonymous"], 0),
            mc_q(
                "mc7",
                "After approval, insurer will:",
                ["Pay claim", "Cancel policy", "Issue fine", "Ignore you"],
                0,
            ),
            tf_q("tf8", "You must always file a claim.", False),
            tf_q("tf9", "False info can deny a claim.", True),
            tf_q("tf10", "Adjusters evaluate claims.", True),
        ],
        "what_is_coverage": [
            mc_q(
                "mc1",
                "Coverage refers to:",
                ["Deductible", "What insurance pays for", "Premium", "Claim form"],
                1,
            ),
            mc_q(
                "mc2",
                "More coverage usually means:",
                ["Higher protection", "Lower cost", "Less safety", "No benefit"],
                0,
            ),
            mc_q(
                "mc3",
                "Coverage limits are:",
                ["Maximum payouts", "Minimum premiums", "Fees", "Discounts"],
                0,
            ),
            mc_q(
                "mc4",
                "Coverage varies by:",
                ["Policy", "Driver", "State", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Insufficient coverage can lead to:",
                ["Out-of-pocket costs", "Refunds", "Discounts", "Free repairs"],
                0,
            ),
            mc_q(
                "mc6",
                "Coverage applies only to:",
                ["Covered events", "All damage", "Any loss", "Any driver"],
                0,
            ),
            mc_q(
                "mc7",
                "Coverage types include:",
                ["Liability", "Collision", "Comprehensive", "All of the above"],
                3,
            ),
            tf_q("tf8", "Coverage is unlimited.", False),
            tf_q("tf9", "Coverage details are in the policy.", True),
            tf_q("tf10", "More coverage usually costs more.", True),
        ],
        "types_of_coverage_for_auto_insurance": [
            mc_q(
                "mc1",
                "Liability covers:",
                ["Your car", "Others’ damages", "Maintenance", "Theft"],
                1,
            ),
            mc_q(
                "mc2",
                "Collision covers:",
                ["Weather damage", "Accidents", "Theft", "Vandalism"],
                1,
            ),
            mc_q(
                "mc3",
                "Comprehensive covers:",
                ["Collisions only", "Non-collision damage", "Tickets", "Oil changes"],
                1,
            ),
            mc_q(
                "mc4",
                "Medical payments cover:",
                ["Vehicle repairs", "Injuries", "Theft", "Rentals"],
                1,
            ),
            mc_q(
                "mc5",
                "Uninsured motorist covers:",
                ["You only", "Others without insurance", "Police", "Mechanics"],
                1,
            ),
            mc_q(
                "mc6",
                "Required coverage varies by:",
                ["State", "Age", "Gender", "Car color"],
                0,
            ),
            mc_q("mc7", "Optional coverage adds:", ["Protection", "Risk", "Penalties", "Tickets"], 0),
            tf_q("tf8", "Liability is mandatory in most states.", True),
            tf_q("tf9", "Collision is always required.", False),
            tf_q("tf10", "Coverage types protect different risks.", True),
        ],
        "factors_affecting_insurance_rates": [
            mc_q(
                "mc1",
                "Rates depend on:",
                ["Driving history", "Age", "Location", "All of the above"],
                3,
            ),
            mc_q("mc2", "Young drivers often pay:", ["Less", "More", "Same", "Nothing"], 1),
            mc_q(
                "mc3",
                "Expensive cars usually have:",
                ["Lower rates", "Higher rates", "No effect", "Free coverage"],
                1,
            ),
            mc_q(
                "mc4",
                "Credit history can affect:",
                ["Rates", "License", "Car value", "Deductible"],
                0,
            ),
            mc_q("mc5", "Urban drivers often pay:", ["Less", "More", "Same", "Nothing"], 1),
            mc_q(
                "mc6",
                "Mileage affects:",
                ["Risk", "Premiums", "Claims", "All of the above"],
                3,
            ),
            mc_q("mc7", "Insurance companies assess:", ["Risk", "Looks", "Personality", "Luck"], 0),
            tf_q("tf8", "Rates are the same for everyone.", False),
            tf_q("tf9", "Riskier drivers pay more.", True),
            tf_q("tf10", "Rates can change over time.", True),
        ],
        "impact_of_driving_history_on_rates": [
            mc_q("mc1", "Accidents usually:", ["Lower rates", "Raise rates", "No effect", "Cancel license"], 1),
            mc_q(
                "mc2",
                "Tickets affect rates by:",
                ["Increasing risk", "Lowering premiums", "Offering discounts", "Fixing credit"],
                0,
            ),
            mc_q(
                "mc3",
                "Clean history often leads to:",
                ["Discounts", "Penalties", "Cancellations", "Fines"],
                0,
            ),
            mc_q(
                "mc4",
                "DUI convictions:",
                ["Lower rates", "Greatly increase rates", "No effect", "Reduce coverage"],
                1,
            ),
            mc_q("mc5", "Insurers review history for:", ["Risk", "Fun", "Speed", "Color"], 0),
            mc_q(
                "mc6",
                "Minor violations usually:",
                ["Have no impact", "Slight impact", "Huge impact", "Cancel insurance"],
                1,
            ),
            mc_q(
                "mc7",
                "Driving history includes:",
                ["Accidents", "Tickets", "Claims", "All of the above"],
                3,
            ),
            tf_q("tf8", "History stays forever.", False),
            tf_q("tf9", "Good history saves money.", True),
            tf_q("tf10", "Bad history raises premiums.", True),
        ],
        "how_to_maintain_a_clean_driving_record": [
            mc_q(
                "mc1",
                "Obeying laws helps:",
                ["Avoid tickets", "Save money", "Reduce accidents", "All of the above"],
                3,
            ),
            mc_q(
                "mc2",
                "Defensive driving reduces:",
                ["Risk", "Accidents", "Claims", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "Avoiding distractions means:",
                ["Texting", "Calling", "Focusing", "Speeding"],
                2,
            ),
            mc_q(
                "mc4",
                "Speeding increases:",
                ["Risk", "Tickets", "Insurance costs", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Traffic school may:",
                ["Remove points", "Add points", "Cancel license", "Raise rates"],
                0,
            ),
            mc_q(
                "mc6",
                "Driving sober helps:",
                ["Safety", "Record", "Rates", "All of the above"],
                3,
            ),
            mc_q(
                "mc7",
                "Awareness prevents:",
                ["Accidents", "Claims", "Tickets", "All of the above"],
                3,
            ),
            tf_q("tf8", "Safe driving has no benefits.", False),
            tf_q("tf9", "Clean records lower rates.", True),
            tf_q("tf10", "Habits affect insurance.", True),
        ],
        "common_auto_insurance_terms_explained": [
            mc_q("mc1", "Premium means:", ["Payment", "Claim", "Deductible", "Coverage"], 0),
            mc_q(
                "mc2",
                "Deductible means:",
                ["Fee before payout", "Refund", "Discount", "Fine"],
                0,
            ),
            mc_q(
                "mc3",
                "Policyholder is:",
                ["Insurer", "Driver", "Owner of policy", "Adjuster"],
                2,
            ),
            mc_q("mc4", "Claim is:", ["Request for payment", "Policy", "Deductible", "Premium"], 0),
            mc_q(
                "mc5",
                "Coverage limit is:",
                ["Max payout", "Min payment", "Fee", "Discount"],
                0,
            ),
            mc_q("mc6", "Adjuster:", ["Sells cars", "Evaluates claims", "Issues tickets", "Repairs vehicles"], 1),
            mc_q("mc7", "Liability means:", ["Responsibility", "Damage", "Theft", "Bonus"], 0),
            tf_q("tf8", "Insurance terms have legal meaning.", True),
            tf_q("tf9", "Understanding terms helps decisions.", True),
            tf_q("tf10", "Policies explain terms.", True),
        ],
        "how_to_choose_the_right_insurance_plan": [
            mc_q(
                "mc1",
                "First step in choosing a plan:",
                ["Pick cheapest", "Assess needs", "Ask friends", "Ignore coverage"],
                1,
            ),
            mc_q(
                "mc2",
                "Coverage should match:",
                ["Budget", "Risk", "Vehicle value", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "Comparing plans helps:",
                ["Save money", "Get better coverage", "Avoid gaps", "All of the above"],
                3,
            ),
            mc_q(
                "mc4",
                "Deductibles affect:",
                ["Premium", "Out-of-pocket costs", "Risk", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Older cars may need:",
                ["More coverage", "Less coverage", "No insurance", "Only liability"],
                1,
            ),
            mc_q(
                "mc6",
                "Discounts should be:",
                ["Ignored", "Asked about", "Avoided", "Hidden"],
                1,
            ),
            mc_q(
                "mc7",
                "Policy limits protect against:",
                ["Small losses", "Large expenses", "Tickets", "Inspections"],
                1,
            ),
            tf_q("tf8", "Cheapest plan is always best.", False),
            tf_q("tf9", "Needs change over time.", True),
            tf_q("tf10", "Comparing quotes is helpful.", True),
        ],
        "importance_of_liability_coverage": [
            mc_q(
                "mc1",
                "Liability covers:",
                ["Your injuries", "Others’ damages", "Maintenance", "Theft"],
                1,
            ),
            mc_q(
                "mc2",
                "Liability is required in:",
                ["Most states", "All countries", "No states", "Only cities"],
                0,
            ),
            mc_q(
                "mc3",
                "Without liability, you may pay:",
                ["Nothing", "Out of pocket", "Less premium", "Discounts"],
                1,
            ),
            mc_q(
                "mc4",
                "Liability includes:",
                ["Bodily injury", "Property damage", "Legal costs", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Low limits can result in:",
                ["Financial risk", "Safety", "Savings", "Refunds"],
                0,
            ),
            mc_q(
                "mc6",
                "Liability protects against:",
                ["Lawsuits", "Tickets", "Theft", "Repairs"],
                0,
            ),
            mc_q(
                "mc7",
                "Higher limits offer:",
                ["More protection", "Less coverage", "More risk", "No benefit"],
                0,
            ),
            tf_q("tf8", "Liability protects you legally.", True),
            tf_q("tf9", "Liability covers your own car.", False),
            tf_q("tf10", "Liability limits matter.", True),
        ],
        "understanding_comprehensive_and_collision_coverage": [
            mc_q(
                "mc1",
                "Collision covers:",
                ["Accidents", "Theft", "Weather", "Fire"],
                0,
            ),
            mc_q(
                "mc2",
                "Comprehensive covers:",
                ["Crashes only", "Non-collision damage", "Tickets", "Maintenance"],
                1,
            ),
            mc_q(
                "mc3",
                "Hitting a deer is:",
                ["Collision", "Comprehensive", "Liability", "Medical"],
                1,
            ),
            mc_q(
                "mc4",
                "Collision usually applies when:",
                ["Another car is involved", "Object impact", "Single-car accident", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Comprehensive includes:",
                ["Theft", "Vandalism", "Weather damage", "All of the above"],
                3,
            ),
            mc_q(
                "mc6",
                "Both cover:",
                ["Your vehicle", "Others’ vehicles", "Injuries", "Lawsuits"],
                0,
            ),
            mc_q(
                "mc7",
                "These coverages are:",
                ["Optional", "Required everywhere", "Free", "Illegal"],
                0,
            ),
            tf_q("tf8", "Comprehensive covers floods.", True),
            tf_q("tf9", "Collision covers theft.", False),
            tf_q("tf10", "Both usually have deductibles.", True),
        ],
        "how_to_lower_your_insurance_premiums": [
            mc_q(
                "mc1",
                "Safe driving can:",
                ["Raise rates", "Lower premiums", "Cancel insurance", "Increase claims"],
                1,
            ),
            mc_q(
                "mc2",
                "Raising deductibles usually:",
                ["Raises premium", "Lowers premium", "No effect", "Cancels policy"],
                1,
            ),
            mc_q(
                "mc3",
                "Bundling policies may:",
                ["Increase cost", "Offer discounts", "Remove coverage", "Add fees"],
                1,
            ),
            mc_q(
                "mc4",
                "Good credit can:",
                ["Increase rates", "Lower rates", "Cancel policy", "Remove coverage"],
                1,
            ),
            mc_q(
                "mc5",
                "Reducing mileage helps:",
                ["Risk", "Premiums", "Claims", "All of the above"],
                3,
            ),
            mc_q(
                "mc6",
                "Comparing insurers helps:",
                ["Find savings", "Waste time", "Increase rates", "Remove discounts"],
                0,
            ),
            mc_q(
                "mc7",
                "Discounts are often for:",
                ["Safe drivers", "Students", "Multiple policies", "All of the above"],
                3,
            ),
            tf_q("tf8", "Premiums can never change.", False),
            tf_q("tf9", "Behavior affects cost.", True),
            tf_q("tf10", "Discounts are automatic.", False),
        ],
        "seasonal_driving_tips_and_insurance_implications": [
            mc_q(
                "mc1",
                "Winter driving increases risk due to:",
                ["Ice", "Snow", "Visibility", "All of the above"],
                3,
            ),
            mc_q(
                "mc2",
                "Summer driving risks include:",
                ["Heat", "Long trips", "Tire blowouts", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "Seasonal accidents may lead to:",
                ["Claims", "Rate increases", "Repairs", "All of the above"],
                3,
            ),
            mc_q(
                "mc4",
                "Proper tires improve:",
                ["Safety", "Control", "Accident prevention", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Weather-related damage is often:",
                ["Collision", "Comprehensive", "Liability", "Medical"],
                1,
            ),
            mc_q(
                "mc6",
                "Seasonal maintenance helps:",
                ["Reduce risk", "Avoid claims", "Save money", "All of the above"],
                3,
            ),
            mc_q(
                "mc7",
                "Poor weather requires:",
                ["Faster driving", "More caution", "Less attention", "No change"],
                1,
            ),
            tf_q("tf8", "Weather affects accident risk.", True),
            tf_q("tf9", "Insurance ignores seasons.", False),
            tf_q("tf10", "Preparedness reduces claims.", True),
        ],
        "impact_of_traffic_violations_on_insurance_rates": [
            mc_q(
                "mc1",
                "Speeding tickets usually:",
                ["Lower rates", "Raise rates", "No effect", "Cancel license"],
                1,
            ),
            mc_q(
                "mc2",
                "Multiple violations show:",
                ["Low risk", "High risk", "No risk", "Safety"],
                1,
            ),
            mc_q(
                "mc3",
                "Serious violations include:",
                ["DUI", "Reckless driving", "Hit-and-run", "All of the above"],
                3,
            ),
            mc_q(
                "mc4",
                "Points on license affect:",
                ["Rates", "Coverage", "Risk level", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Violations stay on record for:",
                ["A period of time", "One day", "Forever", "Never"],
                0,
            ),
            mc_q(
                "mc6",
                "Clean driving helps:",
                ["Lower rates", "Get discounts", "Reduce risk", "All of the above"],
                3,
            ),
            mc_q(
                "mc7",
                "Insurance companies view violations as:",
                ["Risk indicators", "Rewards", "Irrelevant", "Discounts"],
                0,
            ),
            tf_q("tf8", "One ticket has no impact.", False),
            tf_q("tf9", "Violations affect premiums.", True),
            tf_q("tf10", "Good driving can offset past mistakes.", True),
        ],
        "how_to_read_your_insurance_policy": [
            mc_q(
                "mc1",
                "Policy explains:",
                ["Coverage", "Limits", "Exclusions", "All of the above"],
                3,
            ),
            mc_q(
                "mc2",
                "Declarations page shows:",
                ["Premium", "Coverage", "Insured vehicle", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "Exclusions list:",
                ["What’s covered", "What’s not covered", "Discounts", "Claims"],
                1,
            ),
            mc_q("mc4", "Limits define:", ["Maximum payout", "Minimum payment", "Fees", "Refunds"], 0),
            mc_q("mc5", "Endorsements:", ["Change policy", "Cancel coverage", "Ignore rules", "Raise tickets"], 0),
            mc_q(
                "mc6",
                "Reading policy helps avoid:",
                ["Surprises", "Gaps", "Confusion", "All of the above"],
                3,
            ),
            mc_q("mc7", "Policies are legally:", ["Binding", "Optional", "Informal", "Suggestions"], 0),
            tf_q("tf8", "Policies are easy to guess.", False),
            tf_q("tf9", "Reading helps understanding.", True),
            tf_q("tf10", "Policies vary by insurer.", True),
        ],
        "benefits_of_bundling_insurance_policies": [
            mc_q(
                "mc1",
                "Bundling means:",
                ["One policy", "Multiple policies together", "Cancel coverage", "Increase cost"],
                1,
            ),
            mc_q(
                "mc2",
                "Common bundles include:",
                ["Auto + home", "Auto + renters", "Auto + life", "All of the above"],
                3,
            ),
            mc_q("mc3", "Bundling often provides:", ["Discounts", "Penalties", "Fines", "Cancellations"], 0),
            mc_q(
                "mc4",
                "Bundling simplifies:",
                ["Billing", "Management", "Payments", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Bundling may improve:",
                ["Loyalty benefits", "Savings", "Convenience", "All of the above"],
                3,
            ),
            mc_q(
                "mc6",
                "Not all insurers offer:",
                ["Bundling", "Coverage", "Policies", "Claims"],
                0,
            ),
            mc_q(
                "mc7",
                "Bundling works best when:",
                ["Policies fit needs", "Cheapest option", "Required", "Forced"],
                0,
            ),
            tf_q("tf8", "Bundling always costs more.", False),
            tf_q("tf9", "Bundling can save money.", True),
            tf_q("tf10", "Bundling reduces paperwork.", True),
        ],
        "understanding_no_fault_insurance": [
            mc_q(
                "mc1",
                "No-fault means:",
                ["No one pays", "Each driver uses own insurance", "Police decide fault", "No claims allowed"],
                1,
            ),
            mc_q("mc2", "No-fault applies mainly to:", ["Property damage", "Injuries", "Theft", "Tickets"], 1),
            mc_q(
                "mc3",
                "States with no-fault require:",
                ["PIP coverage", "Liability only", "Collision only", "No insurance"],
                0,
            ),
            mc_q(
                "mc4",
                "PIP stands for:",
                ["Personal Injury Protection", "Policy Insurance Plan", "Premium Increase Program", "Private Insurance Policy"],
                0,
            ),
            mc_q("mc5", "No-fault reduces:", ["Lawsuits", "Claims", "Accidents", "Premiums"], 0),
            mc_q(
                "mc6",
                "Drivers still may sue for:",
                ["Severe injuries", "Property damage", "Fraud", "All of the above"],
                0,
            ),
            mc_q("mc7", "No-fault laws vary by:", ["State", "City", "Driver", "Insurer"], 0),
            tf_q("tf8", "No-fault means no responsibility.", False),
            tf_q("tf9", "No-fault applies everywhere.", False),
            tf_q("tf10", "PIP covers medical costs.", True),
        ],
        "what_to_do_in_case_of_a_total_loss": [
            mc_q(
                "mc1",
                "Total loss means:",
                ["Car stolen", "Repair cost exceeds value", "Minor damage", "Flat tire"],
                1,
            ),
            mc_q(
                "mc2",
                "Insurer determines total loss using:",
                ["Market value", "Repair costs", "State rules", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "After total loss, insurer pays:",
                ["Original price", "Actual cash value", "Replacement cost", "Premium"],
                1,
            ),
            mc_q(
                "mc4",
                "Gap insurance helps if:",
                ["Car is old", "Loan exceeds value", "Repairs cheap", "Policy expired"],
                1,
            ),
            mc_q(
                "mc5",
                "You may need to:",
                ["Transfer title", "Remove plates", "Cancel registration", "All of the above"],
                3,
            ),
            mc_q(
                "mc6",
                "Salvage vehicles are:",
                ["Repaired cheaply", "Severely damaged", "Brand new", "Rental cars"],
                1,
            ),
            mc_q(
                "mc7",
                "Total loss settlements can be:",
                ["Negotiated", "Fixed", "Random", "Ignored"],
                0,
            ),
            tf_q("tf8", "Total loss means no compensation.", False),
            tf_q("tf9", "ACV is based on depreciation.", True),
            tf_q("tf10", "Gap insurance is optional.", True),
        ],
        "how_to_handle_uninsured_motorist_situations": [
            mc_q(
                "mc1",
                "Uninsured motorists lack:",
                ["License", "Insurance", "Registration", "Vehicle"],
                1,
            ),
            mc_q(
                "mc2",
                "Uninsured motorist coverage protects:",
                ["Other driver", "You", "Police", "Insurer"],
                1,
            ),
            mc_q(
                "mc3",
                "Hit-and-run incidents may use:",
                ["Collision", "Uninsured coverage", "Liability", "Comprehensive"],
                1,
            ),
            mc_q(
                "mc4",
                "UM coverage may pay for:",
                ["Injuries", "Damage", "Medical bills", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Police reports help:",
                ["Claims", "Proof", "Documentation", "All of the above"],
                3,
            ),
            mc_q(
                "mc6",
                "UM coverage is required in:",
                ["Some states", "All states", "No states", "Every country"],
                0,
            ),
            mc_q(
                "mc7",
                "UM reduces risk of:",
                ["Paying out of pocket", "Claims", "Accidents", "Tickets"],
                0,
            ),
            tf_q("tf8", "Uninsured drivers are rare.", False),
            tf_q("tf9", "UM coverage is useful.", True),
            tf_q("tf10", "Hit-and-run qualifies as uninsured.", True),
        ],
        "understanding_policy_endorsements": [
            mc_q("mc1", "Endorsements are:", ["Policy changes", "Claims", "Discounts", "Deductibles"], 0),
            mc_q(
                "mc2",
                "Endorsements can:",
                ["Add coverage", "Remove coverage", "Modify limits", "All of the above"],
                3,
            ),
            mc_q("mc3", "Endorsements are part of:", ["Policy", "Claim", "Premium", "Deductible"], 0),
            mc_q(
                "mc4",
                "Adding endorsements may:",
                ["Change cost", "Change protection", "Change limits", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Common endorsement example:",
                ["Rental coverage", "Liability", "Deductible", "Claim"],
                0,
            ),
            mc_q("mc6", "Endorsements should be:", ["Reviewed", "Ignored", "Hidden", "Avoided"], 0),
            mc_q("mc7", "Endorsements are legally:", ["Binding", "Optional", "Informal", "Suggested"], 0),
            tf_q("tf8", "Endorsements automatically apply.", False),
            tf_q("tf9", "Endorsements customize coverage.", True),
            tf_q("tf10", "Endorsements appear in policy.", True),
        ],
        "how_to_dispute_a_denied_claim": [
            mc_q(
                "mc1",
                "First step in dispute:",
                ["Sue immediately", "Review denial letter", "Cancel policy", "Ignore insurer"],
                1,
            ),
            mc_q(
                "mc2",
                "Denials often occur due to:",
                ["Exclusions", "Lapsed coverage", "Missing info", "All of the above"],
                3,
            ),
            mc_q(
                "mc3",
                "Supporting documents include:",
                ["Photos", "Reports", "Receipts", "All of the above"],
                3,
            ),
            mc_q(
                "mc4",
                "Appeals should be:",
                ["Written", "Clear", "Timely", "All of the above"],
                3,
            ),
            mc_q(
                "mc5",
                "Adjusters may:",
                ["Re-evaluate claim", "Ignore dispute", "Cancel policy", "Raise premiums"],
                0,
            ),
            mc_q(
                "mc6",
                "If dispute fails, you may:",
                ["File complaint", "Seek mediation", "Consult attorney", "All of the above"],
                3,
            ),
            mc_q(
                "mc7",
                "Staying organized helps:",
                ["Outcome", "Speed", "Clarity", "All of the above"],
                3,
            ),
            tf_q("tf8", "Denied claims are final.", False),
            tf_q("tf9", "Documentation matters.", True),
            tf_q("tf10", "Appeals have deadlines.", True),
        ],
        "understanding_rental_car_coverage": [
            mc_q(
                "mc1",
                "Rental coverage pays for:",
                ["Rental during repairs", "Gas", "Maintenance", "Tickets"],
                0,
            ),
            mc_q(
                "mc2",
                "Rental coverage applies when:",
                ["Claim is covered", "Any accident", "Car serviced", "Policy expires"],
                0,
            ),
            mc_q(
                "mc3",
                "Coverage limits include:",
                ["Daily cap", "Total cap", "Time limit", "All of the above"],
                3,
            ),
            mc_q(
                "mc4",
                "Rental coverage is:",
                ["Required", "Optional", "Illegal", "Automatic"],
                1,
            ),
            mc_q(
                "mc5",
                "Without coverage, rental costs are:",
                ["Free", "Out of pocket", "Discounted", "Refunded"],
                1,
            ),
            mc_q(
                "mc6",
                "Rental companies may offer:",
                ["Insurance", "Waivers", "Add-ons", "All of the above"],
                3,
            ),
            mc_q(
                "mc7",
                "Rental coverage increases:",
                ["Convenience", "Cost slightly", "Protection", "All of the above"],
                3,
            ),
            tf_q("tf8", "Rental coverage pays for luxury cars.", False),
            tf_q("tf9", "Rental coverage has limits.", True),
            tf_q("tf10", "Rental coverage is useful after accidents.", True),
        ],
    }

    title_map = {
        "What is Car Insurance?": "what_is_car_insurance",
        "Understanding Deductibles": "understanding_deductibles",
        "Steps to Take During a Car Accident": "steps_to_take_during_a_car_accident",
        "Do’s and Don’ts of Safe Driving": "dos_and_donts_of_safe_driving",
        "What Is a Premium?": "what_is_a_premium",
        "What Is a Claim?": "what_is_a_claim",
        "How to File a Claim": "how_to_file_a_claim",
        "What Is Coverage?": "what_is_coverage",
        "Types of Coverage for Auto Insurance": "types_of_coverage_for_auto_insurance",
        "Factors Affecting Insurance Rates": "factors_affecting_insurance_rates",
        "Impact of Driving History on Rates": "impact_of_driving_history_on_rates",
        "How to Maintain a Clean Driving Record": "how_to_maintain_a_clean_driving_record",
        "Common Auto Insurance Terms Explained": "common_auto_insurance_terms_explained",
        "How to Choose the Right Insurance Plan": "how_to_choose_the_right_insurance_plan",
        "Importance of Liability Coverage": "importance_of_liability_coverage",
        "Understanding Comprehensive and Collision Coverage": "understanding_comprehensive_and_collision_coverage",
        "How to Lower Your Insurance Premiums": "how_to_lower_your_insurance_premiums",
        "Seasonal Driving Tips and Insurance Implications": "seasonal_driving_tips_and_insurance_implications",
        "Impact of Traffic Violations on Insurance Rates": "impact_of_traffic_violations_on_insurance_rates",
        "How to Read Your Insurance Policy": "how_to_read_your_insurance_policy",
        "Benefits of Bundling Insurance Policies": "benefits_of_bundling_insurance_policies",
        "Understanding No-Fault Insurance": "understanding_no_fault_insurance",
        "What to Do in Case of a Total Loss": "what_to_do_in_case_of_a_total_loss",
        "How to Handle Uninsured Motorist Situations": "how_to_handle_uninsured_motorist_situations",
        "Understanding Policy Endorsements": "understanding_policy_endorsements",
        "How to Dispute a Denied Claim": "how_to_dispute_a_denied_claim",
        "Understanding Rental Car Coverage": "understanding_rental_car_coverage",
    }

    normalized_title = _slugify_topic(module_title)
    canonical_title = title_map.get((module_title or "").strip(), normalized_title)
    bank = bank_by_title.get(canonical_title) or bank_by_title.get(normalized_title)
    if bank:
        return bank

    if normalized_title == "insurance_basics":
        return bank_by_title.get("what_is_car_insurance", [])

    fallback_by_topic = {
        "car_insurance_basics": "what_is_car_insurance",
        "deductible": "understanding_deductibles",
        "accident_steps": "steps_to_take_during_a_car_accident",
        "safe_driving": "dos_and_donts_of_safe_driving",
        "premium": "what_is_a_premium",
        "claim": "what_is_a_claim",
        "claim_filing": "how_to_file_a_claim",
        "coverage": "what_is_coverage",
        "coverage_types": "types_of_coverage_for_auto_insurance",
        "rate_factors": "factors_affecting_insurance_rates",
        "terms": "common_auto_insurance_terms_explained",
        "choose_plan": "how_to_choose_the_right_insurance_plan",
        "liability": "importance_of_liability_coverage",
        "comp_collision": "understanding_comprehensive_and_collision_coverage",
        "discounts": "how_to_lower_your_insurance_premiums",
        "lower_premium": "how_to_lower_your_insurance_premiums",
        "uninsured_motorist": "how_to_handle_uninsured_motorist_situations",
        "endorsements": "understanding_policy_endorsements",
        "denied_claim": "how_to_dispute_a_denied_claim",
        "rental_car": "understanding_rental_car_coverage",
        "total_loss": "what_to_do_in_case_of_a_total_loss",
        "no_fault": "understanding_no_fault_insurance",
    }

    fallback_title = fallback_by_topic.get(topic)
    if fallback_title:
        return bank_by_title.get(fallback_title, [])
    return bank_by_title.get("what_is_car_insurance", [])


@mcp.tool()
def get_knowledge_questions(customer_id: int, limit: int = 3, module_order: int | None = None) -> List[Dict]:
    return get_knowledge_questions_impl(customer_id=customer_id, limit=limit, module_order=module_order)


def get_knowledge_questions_impl(
    customer_id: int,
    limit: int = 3,
    module_order: int | None = None,
    mode: str = "bank",
    seed: str | None = None,
    database_path: str | None = None,
) -> List[Dict]:
    """Return a mixed question bank (MC + True/False) based on the user's curriculum."""

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        curriculum = get_curriculum_impl(int(customer_id))
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path

    bank: List[Dict] = []
    selected_order = int(module_order) if module_order is not None else None

    # If a module is selected, always return the full 10-question bank
    # for that module (per the exact curriculum requirements).
    resolved_limit = int(limit)
    if selected_order is not None and resolved_limit < 10:
        resolved_limit = 10

    mode_l = (mode or "").strip().lower()
    effective_seed = seed if seed is not None else "default"

    for m in curriculum:
        m_order = int(m.get("order"))
        if selected_order is not None and m_order != selected_order:
            continue

        module_title = str(m.get("module"))
        module_description = str(m.get("description"))

        # Modes:
        # - bank/question_bank: deterministic 10-question exact bank (requested behavior)
        # - legacy: older smaller mixed bank
        if mode_l in {"legacy"}:
            bank.extend(
                knowledge_bank_for_module(
                    module_title=module_title,
                    module_description=module_description,
                    module_order=m_order,
                )
            )
        else:
            bank.extend(
                generate_topic_aligned_questions(
                    module_order=m_order,
                    module_title=module_title,
                    module_description=module_description,
                    count=10,
                    seed=effective_seed,
                )
            )

    bank.sort(key=lambda q: (int(q.get("moduleOrder", 0)), str(q.get("id", ""))))
    return bank[: resolved_limit]


@mcp.tool()
def grade_knowledge_answer(customer_id: int, question_id: str, answer: str) -> Dict:
    return grade_knowledge_answer_impl(customer_id=customer_id, question_id=question_id, answer=answer)


def grade_knowledge_answer_impl(
    customer_id: int,
    question_id: str,
    answer: str,
    database_path: str | None = None,
) -> Dict:
    """Grade a knowledge validation answer and return scoring details."""

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        bank = get_knowledge_questions_impl(
            customer_id=int(customer_id),
            limit=200,
            module_order=None,
            mode="bank",
            seed=None,
            database_path=None,
        )
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path

    q = next((x for x in bank if x.get("id") == question_id), None)
    if not q:
        raise ValueError("Unknown question_id")

    q_type = str(q.get("type", "multiple_choice"))
    choices = q.get("choices") if isinstance(q.get("choices"), list) else []
    correct_index = int(q.get("correctIndex", 0))
    expected = q.get("expected") or (choices[correct_index] if choices else None)

    ans = (answer or "").strip()
    ans_l = ans.lower()
    selected_index: int | None = None

    if q_type == "multiple_choice":
        if ans_l in {"a", "b", "c", "d"}:
            selected_index = ord(ans_l) - ord("a")
        elif ans.isdigit() and 1 <= int(ans) <= 4:
            selected_index = int(ans) - 1
        else:
            for idx, choice in enumerate(choices):
                if ans_l == str(choice).strip().lower():
                    selected_index = idx
                    break
    else:
        if ans_l in {"true", "t", "a"}:
            selected_index = 0
        elif ans_l in {"false", "f", "b"}:
            selected_index = 1

    correct = selected_index == correct_index
    weight = float(q.get("weight", knowledge_question_weight(q_type)))
    score = weight if correct else 0.0

    try:
        log_feedback_event_impl(
            customer_id=int(customer_id),
            agent_name="knowledge_validation",
            event_type="graded",
            payload={
                "questionId": str(question_id),
                "correct": bool(correct),
                "score": float(score),
            },
        )
    except Exception:
        pass

    return {
        "questionId": str(question_id),
        "correct": bool(correct),
        "score": float(score),
        "expected": expected,
        "explanation": q.get("explanation", ""),
        "weight": weight,
    }


@mcp.tool()
def start_knowledge_quiz_attempt(
    customer_id: int, questions_limit: int = 10, module_order: int | None = None
) -> Dict:
    return start_knowledge_quiz_attempt_impl(
        customer_id=customer_id, questions_limit=questions_limit, module_order=module_order
    )


def start_knowledge_quiz_attempt_impl(
    customer_id: int,
    questions_limit: int = 10,
    module_order: int | None = None,
    database_path: str | None = None,
) -> Dict:
    """Create a new knowledge quiz attempt and persist it."""

    with connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        plan_row = conn.execute(
            "SELECT id FROM curriculum_plans WHERE customer_id = ? ORDER BY id DESC LIMIT 1;",
            (int(customer_id),),
        ).fetchone()
    if plan_row is None:
        raise ValueError("No curriculum plan found for customer")

    plan_id = int(plan_row["id"])
    questions = get_knowledge_questions_impl(
        customer_id=int(customer_id),
        limit=int(questions_limit),
        module_order=int(module_order) if module_order is not None else None,
        mode="bank",
        seed="default",
        database_path=database_path,
    )
    questions_count = len(questions)
    points_possible = float(sum(float(q.get("weight", 1.0)) for q in questions))
    now = now_date()
    attempt_id = str(uuid.uuid4())

    with connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_quiz_attempts
                (id, customer_id, plan_id, created_at, module_order,
                 questions_count, points_possible, points_earned,
                 questions_total, questions_answered, total_points, earned_points, mode)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                attempt_id,
                int(customer_id),
                plan_id,
                now,
                int(module_order) if module_order is not None else None,
                int(questions_count),
                float(points_possible),
                0.0,
                int(questions_count),
                0,
                float(points_possible),
                0.0,
                "question_bank",
            ),
        )

    return {
        "attemptId": attempt_id,
        "customerId": int(customer_id),
        "moduleOrder": int(module_order) if module_order is not None else None,
        "questionsCount": int(questions_count),
        "pointsPossible": float(points_possible),
        "pointsEarned": 0.0,
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

    with connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        attempt = conn.execute(
            "SELECT id, customer_id, plan_id, module_order FROM knowledge_quiz_attempts WHERE id = ?;",
            (str(attempt_id),),
        ).fetchone()
    if attempt is None or int(attempt["customer_id"]) != int(customer_id):
        raise ValueError("Unknown attempt_id")

    attempt_module_order = attempt["module_order"]
    attempt_module_order_int = int(attempt_module_order) if attempt_module_order is not None else None

    qid_text = str(question_id or "")
    generation_seed = str(attempt_id)
    if "_default_" in qid_text:
        generation_seed = "default"

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        prior_db_path_local = globals().get("db_path")
        graded = grade_knowledge_answer_impl(
            customer_id=int(customer_id),
            question_id=question_id,
            answer=answer,
            database_path=None,
        )
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        bank = get_knowledge_questions_impl(
            int(customer_id),
            limit=200,
            module_order=attempt_module_order_int,
            mode="bank",
            seed=generation_seed,
        )
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path
    q = next((x for x in bank if x["id"] == question_id), None)
    if not q:
        raise ValueError("Unknown question_id")

    module_order = q.get("moduleOrder")
    q_type = str(q.get("type", "multiple_choice"))
    weight = float(q.get("weight", knowledge_question_weight(q_type)))
    points_earned = float(graded.get("score", 0.0))
    correct = 1 if bool(graded.get("correct")) else 0
    now = now_date()

    result_id = str(uuid.uuid4())
    with connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_quiz_results
                            (id, attempt_id, question_id, module_order, question_type, weight, answer_text, correct, points_earned, earned_points, created_at)
            VALUES
                            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                                float(points_earned),
                now,
            ),
        )

        total = conn.execute(
            "SELECT COALESCE(SUM(points_earned), 0.0) AS total FROM knowledge_quiz_results WHERE attempt_id = ?;",
            (str(attempt_id),),
        ).fetchone()[0]
        conn.execute(
                        """
                        UPDATE knowledge_quiz_attempts
                        SET points_earned = ?, earned_points = ?, questions_answered = (
                            SELECT COUNT(*) FROM knowledge_quiz_results WHERE attempt_id = ?
                        )
                        WHERE id = ?;
                        """,
                        (float(total), float(total), str(attempt_id), str(attempt_id)),
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

    with connect(database_path) as conn:
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

#for, Resource Recommendation Agent
@mcp.tool()
def recommend_resources(customer_id: int, topic: str, state: str | None = None, limit: int = 5) -> List[Dict]:
    return recommend_resources_impl(customer_id=customer_id, topic=topic, state=state, limit=limit)


def recommend_resources_impl(customer_id: int, topic: str, state: str | None = None, limit: int = 5) -> List[Dict]:
    """Return resources for a module topic from a local registry.

    Note: This implementation trusts the curated entries in `verified_resources.json`.
    We only enforce that URLs are well-formed (https://) and records contain the
    expected fields, but we do not attempt live link verification here.
    """

    def normalize_topic(raw: str) -> str:
        t = (raw or "").strip().lower()
        # Normalize curly quotes to ASCII
        t = t.replace("’", "'").replace("“", '"').replace("”", '"')
        # Drop punctuation that commonly differs across UI/DB (keep alphanumerics/spaces)
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        # Collapse whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def load_verified_registry() -> Dict[str, List[Dict]]:
        registry_path = Path(__file__).resolve().parent / "verified_resources.json"
        if not registry_path.exists():
            return {}
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def is_valid_resource(item: Dict) -> bool:
        if not isinstance(item, dict):
            return False
        title = str(item.get("title") or "").strip()
        source = str(item.get("source") or "").strip()
        url = str(item.get("url") or "").strip()
        why = str(item.get("whyItMatches") or "").strip()
        if not title or not source or not url or not why:
            return False
        if not url.startswith("https://"):
            return False
        return True

    normalized_topic = normalize_topic(topic)
    registry = load_verified_registry()
    candidates = registry.get(normalized_topic, []) if normalized_topic else []

    valid = [r for r in candidates if is_valid_resource(r)]

    if not valid:
        resources = [
            {
                "type": "system",
                "title": "No resource found.",
                "source": "System",
                "url": "",
                "whyItMatches": "No resource found.",
            }
        ]
    else:
        resources = valid[: max(1, int(limit or 5))]

    now = now_date()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO recommended_resources (id, customer_id, created_at, state, topic, resources_json)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (str(uuid.uuid4()), int(customer_id), now, None, topic, json.dumps(resources)),
        )

    log_feedback_event_impl(
        customer_id=customer_id,
        agent_name="resource_recommendation",
        event_type="recommended",
        payload={"topic": topic, "count": len(resources)},
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

    first_title = str(items[0].get("title") or "").strip()
    if first_title == "No verified resource found.":
        return {"style": style, "summary": "No verified resource found."}

    if style == "video":
        r = items[0]
        title = (r.get("title") or "this resource").strip()
        summary = (r.get("summary") or r.get("whyItMatches") or "").strip()
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
    now = now_date()
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

    def norm_state_for_location(s: str | None) -> str | None:
        """Normalize state input to a 2-letter USPS code.

        Accepts:
        - 2-letter abbreviation ("CA")
        - full name ("California")
        """
        STATE_NAME_TO_CODE: dict[str, str] = {
            "ALABAMA": "AL",
            "ALASKA": "AK",
            "ARIZONA": "AZ",
            "ARKANSAS": "AR",
            "CALIFORNIA": "CA",
            "COLORADO": "CO",
            "CONNECTICUT": "CT",
            "DELAWARE": "DE",
            "FLORIDA": "FL",
            "GEORGIA": "GA",
            "HAWAII": "HI",
            "IDAHO": "ID",
            "ILLINOIS": "IL",
            "INDIANA": "IN",
            "IOWA": "IA",
            "KANSAS": "KS",
            "KENTUCKY": "KY",
            "LOUISIANA": "LA",
            "MAINE": "ME",
            "MARYLAND": "MD",
            "MASSACHUSETTS": "MA",
            "MICHIGAN": "MI",
            "MINNESOTA": "MN",
            "MISSISSIPPI": "MS",
            "MISSOURI": "MO",
            "MONTANA": "MT",
            "NEBRASKA": "NE",
            "NEVADA": "NV",
            "NEW HAMPSHIRE": "NH",
            "NEW JERSEY": "NJ",
            "NEW MEXICO": "NM",
            "NEW YORK": "NY",
            "NORTH CAROLINA": "NC",
            "NORTH DAKOTA": "ND",
            "OHIO": "OH",
            "OKLAHOMA": "OK",
            "OREGON": "OR",
            "PENNSYLVANIA": "PA",
            "RHODE ISLAND": "RI",
            "SOUTH CAROLINA": "SC",
            "SOUTH DAKOTA": "SD",
            "TENNESSEE": "TN",
            "TEXAS": "TX",
            "UTAH": "UT",
            "VERMONT": "VT",
            "VIRGINIA": "VA",
            "WASHINGTON": "WA",
            "WEST VIRGINIA": "WV",
            "WISCONSIN": "WI",
            "WYOMING": "WY",
        }
        STATE_CODES = set(STATE_NAME_TO_CODE.values())

        raw = (s or "").strip()
        if not raw:
            return None
        cleaned = re.sub(r"[\.,]", " ", raw)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().upper()

        if len(cleaned) == 2 and cleaned.isalpha() and cleaned in STATE_CODES:
            return cleaned
        if cleaned in STATE_NAME_TO_CODE:
            return STATE_NAME_TO_CODE[cleaned]
        return None

    def validate_and_normalize_location(loc: str) -> str:
        """Only accept 'City, State' and normalize state to 2-letter code."""

        raw = (loc or "").strip()
        if not raw:
            raise ValueError("location is required and must be in the form 'City, State'")

        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 2:
            raise ValueError(
                "location must be in the form 'City, State' (example: 'Norfolk, VA' or 'Norfolk, Virginia')"
            )

        city, state = parts[0], parts[1]
        if not city:
            raise ValueError("location city is required (example: 'Norfolk, VA')")
        if not state:
            raise ValueError("location state is required (example: 'Norfolk, VA')")

        st = norm_state_for_location(state)
        if st is None:
            raise ValueError(
                "location state must be a valid US state (2-letter code like 'CA' or full name like 'California')"
            )

        return f"{city}, {st}"

    now = now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if existing is None:
            raise ValueError("report_id not found")

        if location is not None:
            location = validate_and_normalize_location(location)

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

    now = now_date()
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
def assess_severity(injured_count: int, vehicles_drivable: bool | None, notes: str | None) -> Dict:
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

    now = now_date()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = conn.execute("SELECT * FROM accident_reports WHERE id = ?;", (report_id,)).fetchone()
        if report is None:
            raise ValueError("report_id not found")

        vehicles_drivable = None if report["vehicles_drivable"] is None else bool(report["vehicles_drivable"])
        result = assess_severity(
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

    now = now_date()
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

        coverage_type_raw = cust["coverage_type"]
        coverage_type = (coverage_type_raw or "").strip().lower()

        assumptions: list[str] = []
        exclusions: list[str] = []

        is_full_coverage = "full" in coverage_type or "collision" in coverage_type or "comprehensive" in coverage_type
        is_liability_only = ("liability" in coverage_type) and (not is_full_coverage)

        if is_liability_only:
            coverage_summary = (
                "Liability-only coverage usually pays for the OTHER person's car damage and injuries "
                "if you caused the accident. It usually does NOT pay to fix your own car."
            )
            exclusions.append("Damage to your own vehicle is usually not covered with liability-only")
            estimated_deductible = None
            estimated_out = None
        else:
            estimated_deductible = 500.0
            coverage_summary = (
                "Full coverage typically means you have liability PLUS coverage to help repair your own car "
                "(often collision and/or comprehensive). You'll usually pay a deductible before insurance helps."
            )
            assumptions.append("Assuming collision coverage applies to this accident")
            assumptions.append("Deductible amount is an estimate; your policy declarations page is the source of truth")
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
        payload={"reportId": report_id, "coverageType": coverage_type_raw},
    )

    return {
        "reportId": report_id,
        "coverageType": coverage_type_raw,
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

    now = now_date()
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
        has_evidence = bool(evidence)

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
                "evidenceOptionalNote": None
                if has_evidence
                else "Evidence is optional, but adding photos/videos later can speed up the claim.",
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


def packet_to_pdf_bytes(packet: Dict) -> bytes:
    """Create a simple 1-page PDF with the claim packet contents.

    We avoid HTML/render engines and generate a compact, readable PDF with a
    monospaced-font text page so it works in restricted environments.
    """

    customer = (packet or {}).get("customer", {})
    accident = (packet or {}).get("accident", {})

    lines: list[str] = []
    lines.append("Insurance Claim Packet")
    lines.append("")
    lines.append(f"Report ID: {accident.get('reportId')}")
    lines.append("")
    lines.append("Customer")
    lines.append(f"  Name: {customer.get('name')}")
    lines.append(f"  ID: {customer.get('id')}")
    lines.append(f"  State: {customer.get('state')}")
    lines.append(f"  Vehicle: {customer.get('vehicle')}")
    lines.append(f"  Coverage Type: {customer.get('coverageType')}")
    lines.append("")
    lines.append("Accident")
    lines.append(f"  Location: {accident.get('location')}")
    lines.append(f"  Injured Count: {accident.get('injuredCount')}")
    lines.append(f"  Vehicles Drivable: {accident.get('vehiclesDrivable')}")
    lines.append(f"  Notes: {accident.get('notes')}")
    lines.append("")
    evidence_urls = accident.get("evidenceUrls") or []
    lines.append(f"Evidence URLs ({len(evidence_urls)}):")
    for u in evidence_urls:
        lines.append(f"  - {u}")
    if accident.get("evidenceOptionalNote"):
        lines.append("")
        lines.append(f"Note: {accident.get('evidenceOptionalNote')}")
    lines.append("")
    lines.append(f"Created At: {packet.get('createdAt')}")

    text = "\n".join(lines)

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)  

    left = 54
    top = 738
    leading = 14

    def pdf_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    text_lines = text.splitlines()
    max_lines = int(top / leading) - 2
    text_lines = text_lines[:max_lines]

    stream_lines = ["BT", "/F1 11 Tf", f"{left} {top} Td"]
    for i, line in enumerate(text_lines):
        if i > 0:
            stream_lines.append(f"0 -{leading} Td")
        stream_lines.append(f"({pdf_escape(line)}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines)

    page["/Resources"] = page.get("/Resources", {})
    page["/Resources"]["/Font"] = page["/Resources"].get("/Font", {})
    page["/Resources"]["/Font"]["/F1"] = writer._add_object(
        {
            "/Type": "/Font",
            "/Subtype": "/Type1",
            "/BaseFont": "/Courier",
        }
    )

    content_obj = writer._add_object({"/Length": len(stream.encode("utf-8"))})
    content_obj._data = stream.encode("utf-8")  
    page["/Contents"] = content_obj

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


@mcp.tool()
def export_claim_packet_pdf(report_id: str, out_dir: str | None = None) -> Dict:
    """Generate a PDF for the current claim packet and save it locally.

    Returns:
      {reportId, filePath, fileName, contentType}
    """

    return export_claim_packet_pdf_impl(report_id=report_id, out_dir=out_dir)


def export_claim_packet_pdf_impl(report_id: str, out_dir: str | None = None) -> Dict:
    packet_res = prepare_claim_packet_impl(report_id=report_id)
    packet = packet_res.get("packet") or {}

    pdf_bytes = packet_to_pdf_bytes(packet)

    base_dir = out_dir or os.path.join("database", "exports")
    os.makedirs(base_dir, exist_ok=True)
    file_name = f"claim_packet_{report_id}.pdf"
    file_path = os.path.join(base_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    return {
        "reportId": report_id,
        "fileName": file_name,
        "filePath": file_path,
        "contentType": "application/pdf",
        "status": packet_res.get("status"),
    }

#for, Action Plan Agent 
@mcp.tool()
def generate_action_plan(report_id: str) -> Dict:
    return generate_action_plan_impl(report_id=report_id)


def generate_action_plan_impl(report_id: str) -> Dict:
    """Generate next steps + simple timelines for this report."""

    now = now_date()
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

    STATE_NAME_TO_CODE: dict[str, str] = {
        "ALABAMA": "AL",
        "ALASKA": "AK",
        "ARIZONA": "AZ",
        "ARKANSAS": "AR",
        "CALIFORNIA": "CA",
        "COLORADO": "CO",
        "CONNECTICUT": "CT",
        "DELAWARE": "DE",
        "FLORIDA": "FL",
        "GEORGIA": "GA",
        "HAWAII": "HI",
        "IDAHO": "ID",
        "ILLINOIS": "IL",
        "INDIANA": "IN",
        "IOWA": "IA",
        "KANSAS": "KS",
        "KENTUCKY": "KY",
        "LOUISIANA": "LA",
        "MAINE": "ME",
        "MARYLAND": "MD",
        "MASSACHUSETTS": "MA",
        "MICHIGAN": "MI",
        "MINNESOTA": "MN",
        "MISSISSIPPI": "MS",
        "MISSOURI": "MO",
        "MONTANA": "MT",
        "NEBRASKA": "NE",
        "NEVADA": "NV",
        "NEW HAMPSHIRE": "NH",
        "NEW JERSEY": "NJ",
        "NEW MEXICO": "NM",
        "NEW YORK": "NY",
        "NORTH CAROLINA": "NC",
        "NORTH DAKOTA": "ND",
        "OHIO": "OH",
        "OKLAHOMA": "OK",
        "OREGON": "OR",
        "PENNSYLVANIA": "PA",
        "RHODE ISLAND": "RI",
        "SOUTH CAROLINA": "SC",
        "SOUTH DAKOTA": "SD",
        "TENNESSEE": "TN",
        "TEXAS": "TX",
        "UTAH": "UT",
        "VERMONT": "VT",
        "VIRGINIA": "VA",
        "WASHINGTON": "WA",
        "WEST VIRGINIA": "WV",
        "WISCONSIN": "WI",
        "WYOMING": "WY",
    }

    STATE_CODES = set(STATE_NAME_TO_CODE.values())

    def norm_state(s: str | None) -> str | None:
        raw = (s or "").strip()
        if not raw:
            return None
        
        cleaned = re.sub(r"[\.,]", " ", raw)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().upper()

        if len(cleaned) == 2 and cleaned.isalpha() and cleaned in STATE_CODES:
            return cleaned

        if cleaned in STATE_NAME_TO_CODE:
            return STATE_NAME_TO_CODE[cleaned]

        return None

    def get_contact_numbers(state: str | None, routed_to: str) -> list[dict]:
        st = norm_state(state)
        contacts: list[dict] = []
        if routed_to == "emergency_services":
            contacts.append(
                {
                    "type": "emergency",
                    "label": "Emergency services",
                    "phone": "911",
                    "note": "If anyone is injured, in danger, or you need immediate help.",
                }
            )

            if st:
                contacts.append(
                    {
                        "type": "non_emergency_guidance",
                        "label": f"{st}: find non-emergency police/highway patrol contacts",
                        "phone": None,
                        "url": "https://www.usa.gov/state-consumer",
                        "note": "Use this directory to find your state's official public safety contacts.",
                    }
                )
                
        if st:
            contacts.append(
                {
                    "type": "insurance_regulator",
                    "label": f"{st} insurance department (directory)",
                    "phone": None,
                    "url": "https://content.naic.org/state-insurance-departments",
                    "note": "Official directory to find your state's insurance department contact info.",
                }
            )

        contacts.append(
            {
                "type": "local_services",
                "label": "Local services (United Way 211)",
                "phone": "211",
                "url": "https://www.211.org/",
                "note": "For local help finding services (not an emergency line).",
            }
        )
        return contacts

    def infer_state_from_location(location: str | None) -> str | None:
        """Try to infer a US state from a free-form location like 'Norfolk, VA' or
        'Norfolk, Virginia'. Returns a normalized 2-letter code when possible."""

        loc = (location or "").strip()
        if not loc:
            return None

        parts = [p.strip() for p in loc.split(",") if p.strip()]
        if not parts:
            return None

        candidate = parts[-1]
        return norm_state(candidate)

    now = now_date()
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

    inferred_state = infer_state_from_location(report["location"])

    customer_state = None
    if inferred_state is None:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cust = conn.execute("SELECT state FROM customers WHERE id=?;", (int(report["customer_id"]),)).fetchone()
            if cust is not None:
                customer_state = cust["state"]
    else:
        customer_state = inferred_state

    contact_numbers = get_contact_numbers(customer_state, routed_to)

    return {
        "reportId": report_id,
        "routedTo": routed_to,
        "reason": reason,
        "summary": summary,
        "customerState": customer_state,
        "contactNumbers": contact_numbers,
    }

#for, Continuous Improvement & Feedback Agent
@mcp.tool()
def log_feedback_event(customer_id: int | None, agent_name: str, event_type: str, payload: Dict | None = None) -> Dict:
    return log_feedback_event_impl(customer_id=customer_id, agent_name=agent_name, event_type=event_type, payload=payload)


def log_feedback_event_impl(customer_id: int | None, agent_name: str, event_type: str, payload: Dict | None = None) -> Dict:
    """Persist a feedback/telemetry event (no PII beyond customer_id)."""

    event_id = str(uuid.uuid4())
    now = now_date()
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
        stateless = os.getenv("MCP_STATELESS_HTTP", "true").strip().lower() in {"1", "true", "yes", "on"}
        mcp.run(
            transport="http",
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8000")),
            stateless_http=stateless,
        )