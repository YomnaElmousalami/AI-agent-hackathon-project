#imports
from fastmcp import FastMCP
from typing import List, Dict
from datetime import datetime, timezone
import sqlite3
import json
import uuid
import re
from io import BytesIO

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

#Code here is for Learning & Education Mode:
#for user onboarding agent

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

    #may remove later
    if row is None:
        raise ValueError(
            f"Customer {customer_id} not found. Call get_customer_info first to store the profile."
        )

    user_age = int(row["age"])

    curriculum = [
        "What is Car Insurance?",
        "Understanding Deductibles",
        "Steps to Take During a car accident.",
        "Do's and Don'ts of Safe Driving",
        "What is a premium?",
        "What is a claim?",
        "How to file a claim?",
        "What is coverage?",
        "Types of coverage for auto insurance",
        "Factors affecting insurance rates",
        "Understanding the impact of driving history on insurance rates",
        "How to maintain a clean driving record",
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
        "Understanding policy endorsements",
        "How to dispute a denied claim",
        "Understanding rental car coverage",
    ]
    # NOTE: Curriculum is now intentionally fixed to the curated 27-module list
    # provided by the project owner (matches the Teacher Agent video library).
    # If you want age-specific variants later, we can add an opt-in flag.
        
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
    # Keep alnum only to avoid separators; cap length for readability.
    tok = re.sub(r"[^a-zA-Z0-9]", "", raw)
    tok = tok[:32]
    return tok or "default"


def _topic_for_module(module_title: str, module_description: str) -> str:
    """Deterministic mapping from module text -> topic key.

    This is shared by both the legacy static bank and the new generator.
    """

    title_l = (module_title or "").lower()
    desc_l = (module_description or "").lower()
    combined = f"{title_l} {desc_l}".strip()

    topic_keywords: list[tuple[str, list[str]]] = [
        # Curriculum fixed titles (ensure alignment)
        ("car_insurance_basics", ["what is car insurance"]),
        # Driving & safety
        ("accident_steps", ["steps to take", "car accident", " accident", " crash"]),
        (
            "safe_driving",
            [
                "safe driving",
                "do's and don'ts",
                "driving tips",
                "seasonal driving",
                "clean driving record",
            ],
        ),
        (
            "rate_factors",
            [
                "insurance rates",
                "rates",
                "factors affecting",
                "traffic violations",
                "driving history",
                "credit score",
                "telematics",
            ],
        ),
        ("discounts", ["discount", "discounts", "lower your insurance premiums", "bundling"]),
        # Special coverages/situations
        ("uninsured_motorist", ["uninsured motorist"]),
        ("rental_car", ["rental car"]),
        ("roadside", ["roadside assistance"]),
        ("total_loss", ["total loss"]),
        ("gap", ["gap insurance"]),
        ("fraud", ["insurance fraud", " fraud"]),
        # Core policy concepts
        ("deductible", ["deduct"]),
        ("premium", ["premium", "grace period"]),
    # Keep more specific claim-related topics BEFORE the generic "claim".
    ("claim_filing", ["how to file a claim"]),
    ("denied_claim", ["dispute a denied claim", "denied claim"]),
    ("claim", ["claim", "claims process", "file a claim", "dispute"]),
        ("coverage_types", ["types of coverage for auto insurance", "types of coverage"]),
        ("choose_plan", ["choose the right insurance plan", "choose the right"]),
        ("terms", ["terms explained", "auto insurance terms"]),
        ("lower_premium", ["lower your insurance premiums", "lower your premiums"]),
    ("endorsements", ["policy endorsements", "endorsement"]),
        (
            "policy_interpretation",
            ["read your insurance policy", "policy", "declarations", "endorsement"],
        ),
        ("liability", ["liability"]),
        ("coverage", ["types of coverage", "coverage", "coverages", "state minimum"]),
        # Collision/comprehensive should be last because of the generic word "comprehensive"
        (
            "comp_collision",
            ["comprehensive coverage", "collision coverage", " collision", " comprehensive "],
        ),
        # Other/special
        ("vehicle_mods", ["vehicle modifications"]),
        ("maintenance", ["vehicle maintenance"]),
        ("switch_provider", ["switch insurance", "switch providers"]),
        ("no_fault", ["no-fault", "no fault"]),
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

    Contract:
    - Returns `count` questions (default 10).
    - Mix: ~70% multiple-choice, ~30% true/false.
    - Ids are unique per (module_order, seed) so quiz attempts can safely re-fetch.
    - LLM-free.
    """

    mo = int(module_order)
    topic = _topic_for_module(module_title, module_description)
    # For ids we need topic to be a single underscore-delimited token.
    topic_token = _slugify_topic(topic).replace("_", "") or "general"

    # We intentionally avoid Python's built-in hash() because it's randomized per process.
    seed_str = seed or now_date()
    seed_slug = _seed_token(seed_str)

    def qid(kind: str, i: int) -> str:
        return f"kv2_m{mo}_{topic_token}_{seed_slug}_{kind}{i}"  # kv2 = new generator

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

    def tf(i: int, statement: str, correct: bool, explanation: str) -> Dict:
        return {
            "id": qid("tf", i),
            "moduleOrder": mo,
            "topic": topic,
            "type": "true_false",
            "prompt": f"True/False: {statement}",
            "choices": ["True", "False"],
            "correctIndex": 0 if bool(correct) else 1,
            "expected": "True" if bool(correct) else "False",
            "explanation": explanation,
            "weight": 0.5,
        }

    # Templates per topic. We keep these short but specific.
    # NOTE: These topic keys are derived from `_topic_for_module()`. If you add a
    # new topic keyword mapping for the curriculum, add templates here too so
    # quizzes stay aligned with the curriculum modules.
    templates: dict[str, list[Dict]] = {
        "car_insurance_basics": [
            mc(
                1,
                "What is car insurance mainly designed to do?",
                [
                    "Help pay for covered losses and protect you financially",
                    "Pay for routine gas and oil changes",
                    "Guarantee you never have an accident",
                    "Replace your car every year",
                ],
                0,
                "Insurance transfers some financial risk from you to the insurer.",
            ),
            mc(
                2,
                "Which is a common part of an auto policy?",
                ["Coverages + limits + deductibles", "A free maintenance plan", "A loan contract", "A driver score"],
                0,
                "Policies describe what’s covered, up to what limits, and what you pay (deductibles).",
            ),
            tf(1, "Insurance is a contract between you and an insurer.", True, "A policy is a legal contract."),
            tf(2, "Car insurance only matters after an accident.", False, "It also matters for legal compliance and peace of mind."),
        ],
        "accident_steps": [
            mc(
                1,
                "After ensuring everyone’s safety, what’s a good next step at the scene?",
                [
                    "Exchange info and document the scene",
                    "Leave immediately",
                    "Argue to decide fault",
                    "Tell your insurer you already fixed everything",
                ],
                0,
                "Documentation and exchanging info help with claims and safety.",
            ),
            mc(
                2,
                "Which information is most useful to collect from the other driver?",
                [
                    "Name, contact info, insurer, policy number, vehicle plate",
                    "Their social media handle",
                    "Their favorite restaurant",
                    "Only their first name",
                ],
                0,
                "Insurance and vehicle details are key for reporting.",
            ),
            tf(1, "Taking photos of vehicle damage and the intersection can help your claim.", True, "Photos are strong evidence."),
            tf(2, "You should admit fault at the scene to speed everything up.", False, "Stick to facts; let insurers/police determine fault."),
        ],
        "safe_driving": [
            mc(
                1,
                "Which habit best reduces crash risk in bad weather?",
                ["Increase following distance", "Drive faster to get home", "Tailgate", "Turn off headlights"],
                0,
                "Space gives you time to react.",
            ),
            mc(
                2,
                "What’s a common insurance benefit of safe driving?",
                ["Potential lower premiums/discounts", "Free gas", "No need for a license", "Guaranteed zero deductibles"],
                0,
                "Some carriers offer discounts for good driving behavior.",
            ),
            tf(1, "Distracted driving can lead to tickets and higher premiums.", True, "Violations and claims can increase cost."),
            tf(2, "A clean driving record can help with both safety and cost.", True, "Lower risk often means lower price."),
        ],
        "rate_factors": [
            mc(
                1,
                "Which factor commonly affects your auto insurance rate?",
                ["Driving history", "Phone wallpaper", "Shoe size", "Favorite color"],
                0,
                "Past driving behavior is a key risk signal.",
            ),
            mc(
                2,
                "Why might an insurer offer telematics-based pricing?",
                ["To price based on observed driving behavior", "To monitor your music", "To change your engine", "To avoid all claims"],
                0,
                "Usage-based insurance can reflect driving patterns.",
            ),
            tf(1, "Tickets and accidents can increase premiums.", True, "More risk often means higher cost."),
            tf(2, "Your premium is always the same regardless of risk.", False, "Rates are tied to risk and underwriting."),
        ],
        "discounts": [
            mc(
                1,
                "Which is a common way to earn an auto insurance discount?",
                ["Bundling policies", "Driving with headlights off", "Ignoring renewal notices", "Paying late fees"],
                0,
                "Multi-policy bundling is a common discount.",
            ),
            mc(
                2,
                "Which practice can help keep costs down over time?",
                ["Maintain a clean driving record", "Get more tickets", "File unnecessary claims", "Skip comparing quotes"],
                0,
                "Risk and claims frequency affect cost.",
            ),
            tf(1, "Some insurers offer good-student discounts.", True, "It depends on the carrier and eligibility."),
            tf(2, "Discounts never change.", False, "Eligibility can change at renewal."),
        ],
        "claim_filing": [
            mc(
                1,
                "What’s a good first step when filing an auto claim?",
                [
                    "Report the loss and provide basic facts (time, place, what happened)",
                    "Wait until repairs are finished",
                    "Guess the other driver’s policy number",
                    "Change the story if details are missing",
                ],
                0,
                "Start by reporting promptly and sticking to facts.",
            ),
            mc(
                2,
                "Which documentation can help when you file a claim?",
                ["Photos + police report (if applicable) + witness info", "Only your opinion", "Only a meme", "Nothing"],
                0,
                "Evidence helps the insurer evaluate the loss.",
            ),
            tf(1, "It’s generally better to report claims promptly.", True, "Many policies require prompt notice."),
            tf(2, "Filing a claim automatically guarantees payment.", False, "Payment depends on coverage, limits, and exclusions."),
        ],
        "coverage_types": [
            mc(
                1,
                "Which coverage commonly pays for damage to your car from a crash?",
                ["Collision", "Liability", "Property tax", "Registration"],
                0,
                "Collision covers damage to your vehicle from a collision (subject to deductible).",
            ),
            mc(
                2,
                "Comprehensive coverage is most associated with:",
                ["Theft, vandalism, hail, or animal strikes", "Rear-ending another car", "Your premium amount", "Traffic tickets"],
                0,
                "Comprehensive is for many non-collision losses (subject to deductible).",
            ),
            tf(1, "Liability coverage is mainly for injuries/damage you cause to others.", True, "That’s the core purpose."),
            tf(2, "Every coverage has the same deductible.", False, "Deductibles vary and some coverages have none."),
        ],
        "choose_plan": [
            mc(
                1,
                "When choosing an insurance plan, what should you compare?",
                ["Coverages, limits, deductibles, exclusions, and price", "Only the logo", "Only the agent’s favorite", "Only the lowest deductible"],
                0,
                "You want a balance of protection and cost.",
            ),
            mc(
                2,
                "If you drive an older car with low value, one common approach is:",
                ["Consider whether collision/comprehensive still make sense for the cost", "Always buy maximum everything", "Always remove liability", "Never review your policy"],
                0,
                "Coverage choices depend on risk, car value, and budget.",
            ),
            tf(1, "Higher limits generally provide more protection.", True, "More limit can reduce out-of-pocket exposure."),
            tf(2, "The cheapest policy is always the best policy.", False, "Cheap can mean less protection or more exclusions."),
        ],
        "terms": [
            mc(
                1,
                "Which pairing is correct?",
                ["Premium = what you pay; deductible = what you pay first on a covered claim", "Premium = claim; deductible = limit", "Premium = ticket; deductible = discount", "Premium = repair; deductible = refund"],
                0,
                "Premium keeps coverage active; deductible is your share on many covered claims.",
            ),
            mc(
                2,
                "A policy limit is best described as:",
                ["The maximum the insurer will pay for a covered loss", "The amount you pay monthly", "A repair estimate", "A vehicle registration fee"],
                0,
                "Limits cap insurer payment.",
            ),
            tf(1, "An exclusion describes something the policy doesn’t cover.", True, "Exclusions are ‘not covered’ items."),
            tf(2, "A deductible is the same as a policy limit.", False, "They’re different: deductible is your part; limit is insurer cap."),
        ],
        "lower_premium": [
            mc(
                1,
                "Which change often lowers premium (all else equal)?",
                ["Raising your deductible", "Adding more tickets", "Lowering liability limits below legal minimums", "Filing many small claims"],
                0,
                "Higher deductibles can reduce premium because you take on more out-of-pocket risk.",
            ),
            mc(
                2,
                "Which is a smart way to reduce costs without changing coverage?",
                ["Shop/compare quotes at renewal", "Cancel insurance for a month", "Ignore discounts", "Drive uninsured"],
                0,
                "Comparing quotes and asking about discounts can help.",
            ),
            tf(1, "Maintaining a clean driving record can help reduce costs.", True, "Lower risk often means lower rates."),
            tf(2, "Insurance costs never change over time.", False, "Rates can change based on risk, location, and market factors."),
        ],
        "no_fault": [
            mc(
                1,
                "In a no-fault system, a common idea is:",
                ["Your own insurer may pay certain benefits regardless of fault", "Fault never matters for anything", "You can’t file any claims", "Liability coverage is illegal"],
                0,
                "No-fault typically affects how some injury benefits are handled.",
            ),
            mc(
                2,
                "Even in no-fault states, which can still be important?",
                ["Limits and coverage types in your policy", "Your car’s paint color", "Your music playlist", "None of the above"],
                0,
                "You still need to understand your coverages and limits.",
            ),
            tf(1, "No-fault laws vary by state.", True, "Rules differ depending on jurisdiction."),
            tf(2, "‘No-fault’ means no one is ever responsible for damages.", False, "Fault can still matter for property damage and lawsuits depending on rules."),
        ],
        "endorsements": [
            mc(
                1,
                "A policy endorsement is best described as:",
                ["A change/add-on that modifies your policy coverage", "A traffic ticket", "A claim payment", "A deductible"],
                0,
                "Endorsements change policy terms (add/remove/alter coverage).",
            ),
            mc(
                2,
                "If you add a new driver or car, what’s a good step?",
                ["Update the policy so it reflects the new risk", "Keep it secret", "Assume it’s automatically covered", "Wait for a claim"],
                0,
                "Policies must be updated to match reality.",
            ),
            tf(1, "Endorsements can change premium.", True, "Coverage changes can affect price."),
            tf(2, "Endorsements are the same as exclusions.", False, "Endorsements modify terms; exclusions limit coverage."),
        ],
        "denied_claim": [
            mc(
                1,
                "If a claim is denied, what’s a reasonable next step?",
                ["Ask for the written denial reason and review your policy language", "Threaten without reading anything", "Invent new facts", "Stop documenting"],
                0,
                "Start with the reason and the policy terms/exclusions.",
            ),
            mc(
                2,
                "Which is most helpful when disputing a denial?",
                ["Evidence and policy references", "Only anger", "Only rumors", "A random guess"],
                0,
                "Documentation and policy language support your position.",
            ),
            tf(1, "Denials can happen due to exclusions, missed payments, or ineligible losses.", True, "Many reasons are possible."),
            tf(2, "If you disagree with a denial, you can never appeal.", False, "Most insurers have an internal review/appeal process."),
        ],
    }

    base = templates.get(topic)
    if not base:
        # Generic fallback aligned to the module by name.
        base = [
            mc(
                1,
                f"What is the main goal of the topic '{module_title}'?",
                [
                    "Learn an insurance concept and how to apply it",
                    "Pick a new car color",
                    "Learn cooking techniques",
                    "Plan a vacation itinerary",
                ],
                0,
                "This module is part of an insurance curriculum.",
            ),
            mc(
                2,
                "What’s a good first step if you’re unsure about coverage details?",
                ["Review your policy documents and limits", "Assume full coverage for everything", "Ignore it", "Wait for a claim"],
                0,
                "Your declarations page/endorsements define coverage.",
            ),
            tf(1, "Insurance policies can include exclusions.", True, "Exclusions specify what’s not covered."),
            tf(2, "Reading your policy can help you avoid surprises.", True, "Knowing limits/deductibles helps decisions."),
        ]

    # Expand deterministically to reach requested count.
    out: List[Dict] = []
    i = 0
    while len(out) < int(count):
        item = base[i % len(base)]
        # Clone with a new id/index to keep uniqueness across the expanded list.
        i += 1
        cloned = dict(item)
        kind = "mc" if cloned.get("type") == "multiple_choice" else "tf"
        cloned["id"] = qid(kind, i)
        out.append(cloned)

    return out[: int(count)]


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

    if topic == "policy_interpretation":
        return [
            mc(
                "mc1",
                "When reading your auto policy, which section tells you what the insurer will pay for?",
                ["Insuring agreement / coverage section", "Declaration page only", "Marketing brochure", "Vehicle title"],
                0,
                "The coverage/insuring agreement describes what is covered (and under what conditions).",
            ),
            mc(
                "mc2",
                "What do policy limits represent?",
                ["The maximum the insurer will pay (per person/per accident/per claim)", "Your deductible amount", "A required police report", "Your vehicle’s resale value"],
                0,
                "Limits cap how much the insurer will pay for a covered loss.",
            ),
            mc(
                "mc3",
                "An exclusion in a policy is best described as:",
                ["Something the policy does NOT cover", "A discount", "A type of premium", "A guarantee of payment"],
                0,
                "Exclusions list situations/damage the policy won’t cover.",
            ),
            mc(
                "mc4",
                "Where would you usually find your chosen deductibles and coverages summarized?",
                ["Declarations page (Declarations)", "Police report", "Repair invoice", "Driver’s license"],
                0,
                "The declarations page summarizes coverages, limits, deductibles, and named insured/vehicles.",
            ),
            mc(
                "mc5",
                "If two parts of the policy seem to conflict, what’s a good first step?",
                [
                    "Re-read definitions + the relevant coverage and exclusions, then ask the insurer/agent for clarification",
                    "Assume the cheaper outcome",
                    "Ignore exclusions",
                    "Only rely on social media advice",
                ],
                0,
                "Definitions and exclusions matter; when in doubt, ask the insurer/agent and get it in writing.",
            ),
            tf(
                "tf1",
                "The declarations page usually lists your coverages, limits, and deductibles.",
                True,
                "That’s one of the main purposes of the declarations page.",
            ),
            tf(
                "tf2",
                "An exclusion means the insurer is promising to pay for that situation.",
                False,
                "Exclusions mean the opposite: it’s not covered.",
            ),
            tf(
                "tf3",
                "Policy definitions can change how a word like 'insured' or 'vehicle' is interpreted.",
                True,
                "Policies define terms precisely; those definitions control interpretation.",
            ),
            tf(
                "tf4",
                "If something is not covered, paying your deductible will make it covered.",
                False,
                "Deductibles apply to covered claims; they don't create coverage.",
            ),
            tf(
                "tf5",
                "It can help to compare the coverage section with exclusions and conditions when reading a policy.",
                True,
                "Coverage is defined by what’s included AND what’s excluded/limited.",
            ),
        ]

    if topic == "liability":
        return [
            mc(
                "mc1",
                "Liability coverage primarily helps pay for:",
                ["Injuries/damage you cause to others", "Your own car’s collision repairs", "Oil changes", "Your deductible"],
                0,
                "Liability is for harm you cause to others (subject to limits).",
            ),
            mc(
                "mc2",
                "If your state requires liability insurance, that usually means:",
                ["You must carry at least the legal minimum limits", "You must buy comprehensive", "You can't buy collision", "You can skip insurance"],
                0,
                "Most states require minimum liability limits.",
            ),
            mc(
                "mc3",
                "Which is an example of a liability claim?",
                ["You rear-end someone and damage their bumper", "Your windshield cracks from a rock", "A hail storm dents your hood", "Your car is stolen"],
                0,
                "Damaging someone else’s property/injuring someone triggers liability.",
            ),
            mc(
                "mc4",
                "A limit like 25/50/25 most commonly refers to:",
                ["Bodily injury per person / bodily injury per accident / property damage", "Deductible / premium / claim count", "Tire pressure / engine size / mpg", "Road speed limits"],
                0,
                "It’s a shorthand for liability limits.",
            ),
            mc(
                "mc5",
                "If you cause a crash and damages exceed your liability limits, what can happen?",
                ["You may owe the difference out of pocket", "Insurance must pay unlimited amounts", "Your deductible becomes zero", "The claim is automatically denied"],
                0,
                "Limits cap insurer payment; excess can become your responsibility.",
            ),
            tf("tf1", "Liability coverage protects other people, not typically your own car repairs.", True, "That’s the basic purpose."),
            tf("tf2", "Higher liability limits can offer more financial protection.", True, "Higher limits can reduce out-of-pocket exposure."),
            tf("tf3", "Liability coverage usually has a deductible like collision does.", False, "Liability typically doesn’t have a deductible."),
            tf("tf4", "State minimum liability limits are always enough for serious accidents.", False, "Minimums may be too low for large losses."),
            tf("tf5", "Liability can apply to property damage you cause.", True, "Yes—property damage is part of liability."),
        ]

    if topic == "comp_collision":
        return [
            mc(
                "mc1",
                "Collision coverage generally helps pay for:",
                ["Damage to your car from a crash (subject to deductible)", "Medical bills for others", "Your monthly premium", "Traffic tickets"],
                0,
                "Collision is for damage to your own vehicle from a collision.",
            ),
            mc(
                "mc2",
                "Comprehensive coverage generally helps pay for damage from:",
                ["Non-collision events like theft, vandalism, hail", "Only crashes", "Only oil leaks", "Only speeding tickets"],
                0,
                "Comprehensive is for non-collision losses (often called 'other than collision').",
            ),
            mc(
                "mc3",
                "Which scenario is typically a comprehensive claim?",
                ["Your car is stolen", "You hit another car", "You rear-end someone", "You run a red light"],
                0,
                "Theft is usually covered under comprehensive.",
            ),
            mc(
                "mc4",
                "Which scenario is typically a collision claim?",
                ["You hit a guardrail", "A tree branch falls on your car", "A deer scratches your paint while parked", "Your car is stolen"],
                0,
                "Hitting an object/vehicle is typically collision.",
            ),
            mc(
                "mc5",
                "Comprehensive and collision often have:",
                ["Deductibles", "No limits", "No policy terms", "Guaranteed payouts"],
                0,
                "They commonly have deductibles and policy conditions.",
            ),
            tf("tf1", "Collision is for crash-related damage to your car.", True, "That’s the basic definition."),
            tf("tf2", "Comprehensive is only for crashes.", False, "Comprehensive is for non-collision events."),
            tf("tf3", "Hail damage is often handled under comprehensive.", True, "Hail is a common comprehensive loss."),
            tf("tf4", "Comprehensive and collision can be optional depending on the policy/vehicle.", True, "They can be optional, but lenders may require them."),
            tf("tf5", "If you choose a higher deductible, your premium can sometimes be lower.", True, "That tradeoff is common."),
        ]

    if topic == "accident_steps":
        return [
            mc(
                "mc1",
                "Right after a crash, what should you do first?",
                ["Check for injuries and get to safety", "Argue with the other driver", "Drive away immediately", "Post online"],
                0,
                "Safety comes first: check injuries and move to a safe spot if you can.",
            ),
            mc(
                "mc2",
                "Which item is most helpful to document for an accident report/claim?",
                ["Photos of damage + scene", "Only your favorite song", "The weather next week", "A random guess"],
                0,
                "Photos, location, and a timeline help insurers understand what happened.",
            ),
            mc(
                "mc3",
                "When should you exchange information with the other driver?",
                ["After everyone is safe", "Never", "Only if they admit fault", "Only if you have full coverage"],
                0,
                "Once safe, exchange contact/insurance info and stick to facts.",
            ),
            mc(
                "mc4",
                "If police are required/appropriate, you should:",
                ["Call and cooperate, then get the report number", "Wait a week", "Hide details", "Refuse to give any info"],
                0,
                "A police report can help document key facts.",
            ),
            mc(
                "mc5",
                "A good rule when talking about fault at the scene is:",
                ["Share facts; let insurers decide fault", "Sign any document given", "Admit fault immediately", "Blame someone loudly"],
                0,
                "Stick to facts and evidence; fault decisions come later.",
            ),
            tf("tf1", "It’s helpful to take photos after an accident (if it’s safe).", True, "Photos are strong evidence."),
            tf("tf2", "You should exchange insurance information after a crash.", True, "This is a standard step."),
            tf("tf3", "You should leave the scene even if someone is injured.", False, "Leaving can be dangerous and illegal."),
            tf("tf4", "Writing down the time/location can help later.", True, "It supports a clear timeline."),
            tf("tf5", "Reporting promptly can matter for coverage.", True, "Policies often require prompt notice."),
        ]

    if topic == "safe_driving":
        return [
            mc(
                "mc1",
                "What’s a ‘do’ of safe driving?",
                ["Keep a safe following distance", "Text while driving", "Speed in bad weather", "Ignore traffic signs"],
                0,
                "Space gives you time to react and reduces crash risk.",
            ),
            mc(
                "mc2",
                "In rain/snow, you should generally:",
                ["Slow down and increase following distance", "Drive the same speed as dry roads", "Brake late", "Turn off headlights"],
                0,
                "Bad weather reduces traction and visibility.",
            ),
            mc(
                "mc3",
                "Why do safe driving habits matter for insurance?",
                ["They can reduce accidents and keep rates lower", "They guarantee free insurance", "They replace a policy", "They remove all deductibles"],
                0,
                "Fewer violations/claims usually means lower risk (and often lower premiums).",
            ),
            mc(
                "mc4",
                "A ‘don’t’ of safe driving is:",
                ["Driving distracted", "Scanning mirrors", "Using seatbelts", "Stopping at lights"],
                0,
                "Distraction increases crash risk.",
            ),
            mc(
                "mc5",
                "A defensive driving course might help by:",
                ["Improving skills and sometimes earning a discount", "Making tickets disappear automatically", "Changing your deductible", "Canceling claims"],
                0,
                "Some insurers offer discounts for approved courses.",
            ),
            tf("tf1", "Speeding can increase accident risk.", True, "Higher speeds reduce reaction time."),
            tf("tf2", "Safe driving can help keep your insurance rates lower over time.", True, "Rates track risk and history."),
            tf("tf3", "Weather never affects stopping distance.", False, "Rain/snow increases stopping distance."),
            tf("tf4", "Distracted driving can lead to tickets and accidents.", True, "Both can affect rates."),
            tf("tf5", "Seatbelts help reduce injury severity.", True, "They’re a key safety feature."),
        ]

    if topic == "rate_factors":
        return [
            mc(
                "mc1",
                "Which can affect your auto insurance rate?",
                ["Driving history", "Where you live", "How much coverage you buy", "All of the above"],
                3,
                "Rates reflect risk, location, and coverage choices.",
            ),
            mc(
                "mc2",
                "A traffic violation can:",
                ["Increase your premium", "Always lower your premium", "Erase your deductible", "Guarantee claim payment"],
                0,
                "Violations can signal higher risk.",
            ),
            mc(
                "mc3",
                "Why might a higher annual mileage increase rates?",
                ["More time driving can mean more exposure to crashes", "Because insurers dislike road trips", "It changes paint color", "It reduces coverage"],
                0,
                "More exposure can mean higher claim likelihood.",
            ),
            mc(
                "mc4",
                "Telematics programs generally track:",
                ["Driving behavior (speeding/braking/time of day)", "Your car’s resale value", "Your phone contacts", "The weather"],
                0,
                "Usage-based insurance uses driving behavior/usage signals.",
            ),
            mc(
                "mc5",
                "More coverage/ lower deductibles often leads to:",
                ["Higher premiums", "Lower premiums", "No change ever", "Illegal coverage"],
                0,
                "More protection usually costs more.",
            ),
            tf("tf1", "Tickets/accidents can impact your premium.", True, "They’re common rating factors."),
            tf("tf2", "Where you park/garage a vehicle can affect risk.", True, "Location affects theft/crash risk."),
            tf("tf3", "Rates are the same for everyone.", False, "Rates vary by risk factors."),
            tf("tf4", "Coverage selections can change your premium.", True, "More coverage often costs more."),
            tf("tf5", "Driving history is irrelevant to insurance rates.", False, "It’s one of the biggest factors."),
        ]

    if topic == "discounts":
        return [
            mc(
                "mc1",
                "Which is a common way to lower your premium?",
                ["Ask about discounts and adjust deductible/coverage thoughtfully", "File unnecessary claims", "Hide tickets", "Cancel insurance"],
                0,
                "Discounts and smart coverage choices can reduce cost.",
            ),
            mc(
                "mc2",
                "Bundling usually means:",
                ["Buying multiple policies (auto + renters/home) with one insurer", "Adding more deductibles", "Filing two claims", "Driving two cars"],
                0,
                "Bundling can sometimes earn a discount.",
            ),
            mc(
                "mc3",
                "A higher deductible often results in:",
                ["Lower premium but more out-of-pocket if a claim happens", "Lower out-of-pocket always", "Guaranteed payout", "No change"],
                0,
                "You trade lower premiums for higher claim cost to you.",
            ),
            mc(
                "mc4",
                "Which could qualify as a discount?",
                ["Good student / safe driver / multi-policy (depends on insurer)", "Late payments", "Multiple accidents", "Expired license"],
                0,
                "Discounts vary, but safe driving and bundling are common.",
            ),
            mc(
                "mc5",
                "The safest way to shop for savings is to:",
                ["Compare quotes with the same coverages/limits", "Compare random prices with different coverages", "Pick the lowest without reading", "Ignore deductibles"],
                0,
                "Comparisons only make sense when coverage is comparable.",
            ),
            tf("tf1", "Bundling can sometimes reduce premiums.", True, "Many insurers offer multi-policy discounts."),
            tf("tf2", "Raising your deductible can reduce premium.", True, "Common tradeoff."),
            tf("tf3", "Discounts are identical at every insurer.", False, "They vary by insurer and state."),
            tf("tf4", "Comparing quotes requires matching coverages.", True, "Otherwise it’s apples-to-oranges."),
            tf("tf5", "Safe driving can help you earn discounts.", True, "Some programs reward behavior."),
        ]

    if topic == "uninsured_motorist":
        return [
            mc(
                "mc1",
                "Uninsured motorist coverage helps when:",
                ["The at-fault driver has no insurance", "Your car needs gas", "You get a parking ticket", "You cancel your policy"],
                0,
                "It can protect you if the other driver is uninsured.",
            ),
            mc(
                "mc2",
                "What should you do after being hit by an uninsured driver?",
                ["Report the accident and gather evidence", "Leave without info", "Hide the damage", "Wait months"],
                0,
                "Prompt reporting and evidence matter.",
            ),
            mc(
                "mc3",
                "Uninsured motorist may cover:",
                ["Injuries to you/your passengers (varies by state/policy)", "Oil changes", "Your premium payments", "Traffic court fees"],
                0,
                "Coverage details vary, but it can help with injuries and sometimes property damage.",
            ),
            mc(
                "mc4",
                "A key reason to consider this coverage is:",
                ["Not everyone carries enough insurance", "It replaces liability", "It cancels deductibles", "It forces the other driver to pay"],
                0,
                "It’s protection against others’ lack of coverage.",
            ),
            mc(
                "mc5",
                "If the other driver flees (hit-and-run), uninsured motorist may:",
                ["Apply depending on your policy/state", "Never apply", "Always pay instantly", "Replace your premium"],
                0,
                "Many policies treat hit-and-run as uninsured, but rules vary.",
            ),
            tf("tf1", "Uninsured motorist coverage can be useful in a hit-and-run.", True, "Often, but depends on policy/state."),
            tf("tf2", "It’s impossible to be hit by an uninsured driver.", False, "It happens."),
            tf("tf3", "Coverage details can vary by state.", True, "Insurance is state-regulated."),
            tf("tf4", "You should document and report promptly.", True, "Helps establish facts."),
            tf("tf5", "Uninsured motorist is the same as liability coverage.", False, "They serve different purposes."),
        ]

    if topic == "rental_car":
        return [
            mc(
                "mc1",
                "Rental reimbursement typically helps pay for:",
                ["A rental car while your car is being repaired for a covered claim", "Gas forever", "A new car", "Your deductible"],
                0,
                "It can cover rental costs up to a daily/total limit.",
            ),
            mc(
                "mc2",
                "Rental reimbursement usually has:",
                ["Daily and total limits", "Unlimited coverage", "No rules", "No paperwork"],
                0,
                "Policies often cap $/day and max days.",
            ),
            mc(
                "mc3",
                "When would rental coverage apply?",
                ["After a covered loss where your car can’t be used", "For vacations", "Any weekend", "Only when you speed"],
                0,
                "It’s tied to a covered claim.",
            ),
            mc(
                "mc4",
                "Before relying on this, you should check:",
                ["Your policy limits and eligibility", "Your tire brand", "The other driver’s playlist", "Your car’s color"],
                0,
                "Limits and conditions matter.",
            ),
            mc(
                "mc5",
                "If the claim is denied, rental reimbursement typically:",
                ["Wouldn’t apply", "Would still pay", "Becomes liability", "Cancels your premium"],
                0,
                "Coverage generally follows the covered claim.",
            ),
            tf("tf1", "Rental coverage often has a daily limit.", True, "Common structure."),
            tf("tf2", "Rental coverage is usually unrelated to having a covered claim.", False, "It’s usually tied to covered loss."),
            tf("tf3", "You should review limits/terms in your policy.", True, "Always."),
            tf("tf4", "Rental reimbursement is the same as collision.", False, "Different coverage."),
            tf("tf5", "Rental coverage may not be included unless you add it.", True, "Often optional."),
        ]

    if topic == "roadside":
        return [
            mc(
                "mc1",
                "Roadside assistance may help with:",
                ["Towing, flat tire, jump-start (depending on plan)", "Paying your premium", "Replacing your car", "Traffic tickets"],
                0,
                "It’s for common breakdown-related services.",
            ),
            mc(
                "mc2",
                "Roadside assistance is typically:",
                ["Optional add-on or included with some policies", "The same as liability", "Illegal", "Only for new cars"],
                0,
                "Depends on insurer/policy.",
            ),
            mc(
                "mc3",
                "A key thing to check is:",
                ["Service limits and number of uses", "Your paint color", "Your radio station", "Your favorite snack"],
                0,
                "Many plans cap towing miles or calls.",
            ),
            mc(
                "mc4",
                "Roadside assistance primarily addresses:",
                ["Breakdowns, not crash repairs", "Collision repairs", "Medical liability", "Policy limits"],
                0,
                "It’s separate from collision/comprehensive.",
            ),
            mc(
                "mc5",
                "If you also have a car club/credit card roadside benefit, you should:",
                ["Compare benefits so you don’t pay twice", "Assume they’re identical", "Cancel insurance", "Ignore limits"],
                0,
                "Avoid duplicate coverage when possible.",
            ),
            tf("tf1", "Roadside assistance can include towing.", True, "Often included."),
            tf("tf2", "Roadside assistance and collision coverage are the same.", False, "Different purposes."),
            tf("tf3", "Roadside services may have limits.", True, "Common."),
            tf("tf4", "You should know who to call (insurer/app/number).", True, "Helps in emergencies."),
            tf("tf5", "Roadside assistance automatically covers any accident damage.", False, "That’s handled by other coverages."),
        ]

    if topic == "total_loss":
        return [
            mc(
                "mc1",
                "A total loss usually means:",
                ["Repair cost is too high compared to the vehicle’s value", "The car has no tires", "You missed a payment", "You got a ticket"],
                0,
                "Insurers compare repair cost to the car’s value and state rules.",
            ),
            mc(
                "mc2",
                "If your car is totaled, the settlement is often based on:",
                ["Actual cash value (ACV)", "Original sticker price always", "Your monthly premium", "A random number"],
                0,
                "Many policies pay ACV (market value) minus deductible (if applicable).",
            ),
            mc(
                "mc3",
                "If you still owe money on a totaled car, you might consider:",
                ["Gap insurance (if eligible)", "Lowering liability limits", "Skipping documentation", "Ignoring the lender"],
                0,
                "Gap can cover the difference between ACV and loan balance in some cases.",
            ),
            mc(
                "mc4",
                "Asking for the valuation report helps because:",
                ["You can review comparable vehicles and assumptions", "It makes coverage unlimited", "It cancels the deductible", "It changes your premium"],
                0,
                "You can verify comps, condition adjustments, etc.",
            ),
            mc(
                "mc5",
                "If you disagree with the value, a good next step is:",
                ["Provide evidence (comps/condition/records) and ask for review", "Threaten without evidence", "Do nothing", "Delete records"],
                0,
                "Support your position with documentation.",
            ),
            tf("tf1", "Total loss settlements often use actual cash value.", True, "Common policy structure."),
            tf("tf2", "A total loss always means the car is unrecoverable.", False, "It can be repairable but not economical."),
            tf("tf3", "You can ask how the insurer calculated the value.", True, "You can request the valuation details."),
            tf("tf4", "If you have a deductible, it may apply to certain coverages.", True, "Depending on the claim type."),
            tf("tf5", "Keeping maintenance records can help support condition/value.", True, "Documentation helps."),
        ]

    if topic == "fraud":
        return [
            mc(
                "mc1",
                "Insurance fraud is:",
                ["Lying or exaggerating to get paid by insurance", "Paying your premium", "Getting a quote", "Reading your policy"],
                0,
                "Fraud involves intentional deception.",
            ),
            mc(
                "mc2",
                "Which is a red flag you should avoid?",
                ["A shop encouraging you to claim old damage as new", "Taking photos", "Keeping receipts", "Reporting honestly"],
                0,
                "Misrepresenting damage can be fraud.",
            ),
            mc(
                "mc3",
                "A possible consequence of fraud is:",
                ["Denied claim and legal trouble", "Guaranteed payout", "Lower premiums", "Free upgrades"],
                0,
                "Fraud can lead to denial, cancellation, and prosecution.",
            ),
            mc(
                "mc4",
                "If you make an honest mistake on a claim, you should:",
                ["Correct it as soon as possible", "Double down", "Destroy evidence", "Ignore the insurer"],
                0,
                "Prompt correction is best.",
            ),
            mc(
                "mc5",
                "The best approach when reporting is:",
                ["Tell the truth and provide supporting documentation", "Guess details", "Inflate costs", "Copy someone else"],
                0,
                "Accuracy helps claims and avoids issues.",
            ),
            tf("tf1", "Exaggerating damage to get more money is fraud.", True, "That’s a classic example."),
            tf("tf2", "Fraud can affect premiums for everyone.", True, "It increases costs system-wide."),
            tf("tf3", "Fraud has no consequences.", False, "It can be serious."),
            tf("tf4", "Honesty and documentation matter in claims.", True, "Best practice."),
            tf("tf5", "It’s okay to claim damage that didn’t happen in the accident.", False, "That’s misrepresentation."),
        ]

    if topic == "gap":
        return [
            mc(
                "mc1",
                "Gap insurance is most relevant when:",
                ["You owe more on a loan/lease than the car’s value", "You have a slow tire leak", "You want a lower deductible", "You got a ticket"],
                0,
                "It’s designed for loan/lease ‘gap’ scenarios.",
            ),
            mc(
                "mc2",
                "Why might there be a ‘gap’?",
                ["Cars can depreciate faster than the loan balance", "Premiums are too low", "Liability limits are high", "Policies expire early"],
                0,
                "Depreciation can outpace principal payoff.",
            ),
            mc(
                "mc3",
                "Gap coverage typically applies after:",
                ["A total loss covered by the policy", "Any oil change", "A parking ticket", "Switching insurers"],
                0,
                "It’s tied to total loss settlements.",
            ),
            mc(
                "mc4",
                "Gap insurance usually does NOT replace:",
                ["Collision/comprehensive", "A phone plan", "A driver’s license", "A repair invoice"],
                0,
                "It complements your base coverage.",
            ),
            mc(
                "mc5",
                "A good way to know if you need gap is to compare:",
                ["Loan/lease payoff vs current market value", "Your premium vs your deductible", "Your age vs your mileage", "Your tire pressure"],
                0,
                "Compare payoff and vehicle value.",
            ),
            tf("tf1", "Gap insurance is mainly about loan/lease balance vs vehicle value.", True, "That’s the point of gap."),
            tf("tf2", "Gap is most relevant in a total loss scenario.", True, "It applies when the vehicle is totaled."),
            tf("tf3", "Gap insurance is the same as liability.", False, "Different coverages."),
            tf("tf4", "Depreciation can create a gap.", True, "Yes."),
            tf("tf5", "You should review eligibility/terms.", True, "Rules vary by policy/lender."),
        ]

    if topic == "young_driver":
        return [
            mc(
                "mc1",
                "For new drivers, a key way to keep costs down is:",
                ["Drive safely and avoid tickets/accidents", "File lots of claims", "Ignore seatbelts", "Speed to save time"],
                0,
                "Driving history is a major pricing factor.",
            ),
            mc(
                "mc2",
                "A common discount for teen/student drivers is:",
                ["Good student discount (if offered)", "Late payment discount", "Accident discount", "Ticket discount"],
                0,
                "Many insurers offer good student discounts.",
            ),
            mc(
                "mc3",
                "Being listed correctly on a policy matters because:",
                ["It ensures the insurer knows who drives the car", "It lowers deductible to zero", "It guarantees claim payment", "It changes car color"],
                0,
                "Accurate driver info is important for coverage and rating.",
            ),
            mc(
                "mc4",
                "A safe driving course can:",
                ["Improve skills and maybe qualify for a discount", "Remove all limits", "Replace insurance", "Make you immune to accidents"],
                0,
                "Some policies offer discounts for course completion.",
            ),
            mc(
                "mc5",
                "For young drivers, why is insurance often more expensive?",
                ["Less driving experience can mean higher risk", "Because cars are heavier", "Because deductibles are illegal", "Because premiums are random"],
                0,
                "Rates often reflect risk and experience.",
            ),
            tf("tf1", "Tickets can raise premiums for many drivers.", True, "Especially for new drivers."),
            tf("tf2", "Good grades can sometimes help lower premiums.", True, "If the insurer offers a discount."),
            tf("tf3", "It’s okay to leave a regular driver off the policy.", False, "That can create coverage/rating issues."),
            tf("tf4", "Experience and history can affect rates.", True, "Common factor."),
            tf("tf5", "Safe driving habits matter for both safety and cost.", True, "Win-win."),
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
        tf("tf5", "Coverage and cost depend on what you purchased.", True, ""),
    ]


@mcp.tool()
def get_knowledge_questions(customer_id: int, limit: int = 3, module_order: int | None = None) -> List[Dict]:
    return get_knowledge_questions_impl(customer_id=customer_id, limit=limit, module_order=module_order)


def get_knowledge_questions_impl(
    customer_id: int,
    limit: int = 3,
    module_order: int | None = None,
    mode: str = "generated",
    seed: str | None = None,
    database_path: str | None = None,
) -> List[Dict]:
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

    selected_order = int(module_order) if module_order is not None else None

    mode_l = (mode or "").strip().lower()
    # For the new generator, ids depend on the seed. If callers don't pass a seed
    # (e.g., simple previews), we still need stability so grading/recording can
    # re-fetch the same question ids.
    effective_seed = seed if seed is not None else "default"

    for m in curriculum:
        m_order = int(m.get("order"))
        if selected_order is not None and m_order != selected_order:
            continue

        module_title = str(m.get("module"))
        module_description = str(m.get("description"))

        if mode_l in {"legacy", "bank", "question_bank"}:
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

    # IMPORTANT: the question bank is generated per module and concatenated.
    # If ids aren't unique (or the bank differs between fetch and grade), the
    # grader can't find the referenced question id and raises "Unknown question_id".
    # We build a wide bank here (200 questions) and, when possible, narrow by
    # module order encoded in the id format (e.g., 'kv_m3_mc1').
    qid_text = str(question_id or "")

    # Infer module order + generator seed from the question id.
    # Supported formats:
    # - Legacy bank: kv_m3_mc1
    # - New generator: kv2_m3_{topic}_{seed}_mc1
    inferred_module_order: int | None = None
    inferred_seed: str | None = None

    try:
        if qid_text.startswith("kv2_m"):
            # kv2_m{order}_{topicToken}_{seedToken}_{kind}{i}
            # split: [kv2, m{order}, {topicToken}, {seedToken}, rest]
            parts = qid_text.split("_")
            if len(parts) >= 5:
                m_part = parts[1]  # like 'm3'
                if m_part.startswith("m") and m_part[1:].isdigit():
                    inferred_module_order = int(m_part[1:])
                inferred_seed = parts[3] or None
        elif qid_text.startswith("kv_m"):
            # kv_m3_mc1
            tail = qid_text.split("kv_m", 1)[1]
            digits = ""
            for ch in tail:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            inferred_module_order = int(digits) if digits else None
    except Exception:
        inferred_module_order = None
        inferred_seed = None

    # Rebuild a wide-enough bank with the same generator + seed.
    # For generated questions we must use the same seed that produced the id.
    bank_mode = "generated" if qid_text.startswith("kv2_") else "legacy"
    if bank_mode == "generated" and not inferred_seed:
        inferred_seed = "default"
    bank = get_knowledge_questions_impl(
        int(customer_id),
        limit=400,
        module_order=inferred_module_order,
        mode=bank_mode,
        seed=inferred_seed,
        database_path=database_path,
    )
    q = next((x for x in bank if x.get("id") == question_id), None)
    if not q:
        raise ValueError("Unknown question_id")

    expected = str(q.get("expected", ""))
    q_type = str(q.get("type", "multiple_choice"))
    weight = float(q.get("weight", knowledge_question_weight(q_type)))


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
                "moduleOrder": q.get("moduleOrder"),
                "topic": q.get("topic"),
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
    "feedback": "Nice!" if correct else "Not quite",
        "explanation": q.get("explanation", ""),
    }


def get_plan_id_for_customer(customer_id: int, database_path: str | None = None) -> int:
    with connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id FROM curriculum_plans WHERE customer_id = ?;", (int(customer_id),)
        ).fetchone()
    if row is None:
        raise ValueError("No curriculum plan found for this customer.")
    return int(row["id"])


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
    """Create a knowledge validation quiz attempt tied to the customer's curriculum plan.

    This enables saving scores and unlimited reattempts.
    """

    plan_id = get_plan_id_for_customer(int(customer_id), database_path=database_path)
    attempt_id = str(uuid.uuid4())
    now = now_date()

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        qs = get_knowledge_questions_impl(
            int(customer_id),
            limit=int(questions_limit),
            module_order=module_order,
            mode="generated",
            seed=attempt_id,
        )
    finally:
        if database_path is not None:
            globals()["db_path"] = prior_db_path
    points_possible = float(
        sum(
            float(q.get("weight", knowledge_question_weight(str(q.get("type", "")))))
            for q in qs
        )
    )

    with connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_quiz_attempts
                            (
                                id, customer_id, plan_id, created_at, module_order,
                                questions_count, points_possible, points_earned,
                                questions_total, questions_answered, total_points, earned_points,
                                mode
                            )
            VALUES
                            (?, ?, ?, ?, ?, ?, ?, 0.0, ?, 0, ?, 0.0, 'question_bank');
            """,
            (
                attempt_id,
                int(customer_id),
                int(plan_id),
                now,
                int(module_order) if module_order is not None else None,
                int(len(qs)),
                float(points_possible),
                                int(len(qs)),
                                float(points_possible),
            ),
        )

    return {
        "attemptId": attempt_id,
        "customerId": int(customer_id),
        "planId": int(plan_id),
        "moduleOrder": int(module_order) if module_order is not None else None,
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

    # Determine which seed produced this question id.
    # - If the caller fetched questions outside the attempt flow, ids use seed "default".
    # - If they fetched questions for an attempt, we seed by attempt_id.
    qid_text = str(question_id or "")
    generation_seed = str(attempt_id)
    if "_default_" in qid_text:
        generation_seed = "default"

    prior_db_path = globals().get("db_path")
    if database_path is not None:
        globals()["db_path"] = database_path
    try:
        # Grade must use same seed as the attempt question generation.
        # We infer module order from the question id inside the grader.
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
            mode="generated",
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

    now = now_date()
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
        # Postman MCP support expects an SSE-style workflow. In practice, FastMCP's
        # `stateless_http=True` is the most reliable mode on Windows dev machines.
        # You can still force stateful mode by setting MCP_STATELESS_HTTP=false.
        stateless = os.getenv("MCP_STATELESS_HTTP", "true").strip().lower() in {"1", "true", "yes", "on"}
        mcp.run(
            transport="http",
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8000")),
            stateless_http=stateless,
        )