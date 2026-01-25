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


def test_get_questions_and_grade_answer_logs_event(temp_db):
	_seed_customer(temp_db, 1)
	qs = insurance_mcp.get_knowledge_questions_impl(customer_id=1, limit=2)
	assert len(qs) == 2
	q0 = qs[0]

	res = insurance_mcp.grade_knowledge_answer_impl(customer_id=1, question_id=q0["id"], answer="you pay 500")
	assert "score" in res
	assert "expected" in res

	summary = insurance_mcp.get_feedback_summary_impl(customer_id=1, limit=20)
	assert summary["totalEvents"] >= 1
	assert any(
		r["agent"] == "knowledge_validation" for r in summary.get("recent", [])
	)
