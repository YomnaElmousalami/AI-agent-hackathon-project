import os
import sqlite3

import pytest

import insurance_mcp
from database.insurance_db import init_db


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_insurance.db"
    init_db(str(db_file))
    monkeypatch.setattr(insurance_mcp, "db_path", str(db_file))
    return str(db_file)


def _seed_customer(db_path: str, customer_id: int = 1):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, '01/01/2026', '01/01/2026');
            """,
            (customer_id, "Alex", 16, "CA", "Honda Accord", "Liability"),
        )


def _seed_curriculum(db_path: str, customer_id: int = 1):
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            INSERT INTO curriculum_plans (customer_id, customer_age, created_at, updated_at)
            VALUES (?, ?, '01/01/2026', '01/01/2026');
            """,
            (customer_id, 16),
        )
        plan_id = conn.execute(
            "SELECT id FROM curriculum_plans WHERE customer_id = ?;", (customer_id,)
        ).fetchone()[0]
        conn.executemany(
            """
            INSERT INTO curriculum_modules (plan_id, module_order, module_title, module_description, created_at)
            VALUES (?, ?, ?, ?, '01/01/2026');
            """,
            [
                (plan_id, 1, "Understanding Deductibles", "A comprehensive overview of deductibles."),
                (plan_id, 2, "What is a claim?", "A comprehensive overview of claims."),
            ],
        )


def test_generate_flashcards_from_curriculum(temp_db):
    _seed_customer(temp_db, 1)
    _seed_curriculum(temp_db, 1)

    cards = insurance_mcp.generate_flashcards_impl(customer_id=1, module_order=1, limit=50)
    assert len(cards) >= 2
    assert all(c["moduleOrder"] == 1 for c in cards)
    assert any("deductible" in c["back"].lower() for c in cards)


def test_quiz_session_flow(temp_db):
    _seed_customer(temp_db, 1)
    _seed_curriculum(temp_db, 1)

    session = insurance_mcp.start_flashcard_quiz_impl(customer_id=1, module_order=1, limit=10)
    assert "sessionId" in session
    assert session["card"] is not None

    session_id = session["sessionId"]
    first_card = session["card"]

    graded = insurance_mcp.submit_flashcard_answer_impl(
        session_id=session_id, card_id=first_card["cardId"], answer="deductible is what you pay out of pocket"
    )
    assert graded["correct"] in (True, False)
    assert "expected" in graded

    nxt = insurance_mcp.get_next_flashcard_impl(session_id=session_id)
    assert nxt["sessionId"] == session_id
