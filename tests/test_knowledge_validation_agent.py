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


def seed_customer(db_path: str, customer_id: int = 1):
	with sqlite3.connect(db_path) as conn:
		conn.execute(
			"""
			INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?, '01/01/2026', '01/01/2026');
			""",
			(customer_id, "Alex", 16, "CA", "Honda Accord", "Liability"),
		)


def seed_curriculum(db_path: str, customer_id: int = 1):
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
				(
					plan_id,
					1,
					"Understanding Deductibles",
					"A comprehensive overview of deductibles.",
				),
			],
		)


def test_get_questions_and_grade_answer_logs_event(temp_db):
	seed_customer(temp_db, 1)
	seed_curriculum(temp_db, 1)

	qs = insurance_mcp.get_knowledge_questions_impl(customer_id=1, limit=20)
	assert len(qs) == 10
	q0 = qs[0]
	assert q0["type"] in ("multiple_choice", "true_false")
	assert "prompt" in q0
	assert isinstance(q0.get("choices"), list)
	assert q0.get("weight") in (1.0, 0.5)

	mc_q = next(q for q in qs if q["type"] == "multiple_choice")
	tf_q = next(q for q in qs if q["type"] == "true_false")

	mc_correct_ans = mc_q["choices"][mc_q["correctIndex"]]
	mc_res = insurance_mcp.grade_knowledge_answer_impl(
		customer_id=1, question_id=mc_q["id"], answer=mc_correct_ans
	)
	assert mc_res["correct"] is True
	assert mc_res["score"] == 1.0

	tf_correct_ans = tf_q["choices"][tf_q["correctIndex"]]
	tf_res = insurance_mcp.grade_knowledge_answer_impl(
		customer_id=1, question_id=tf_q["id"], answer=tf_correct_ans
	)
	assert tf_res["correct"] is True
	assert tf_res["score"] == 0.5

	summary = insurance_mcp.get_feedback_summary_impl(customer_id=1, limit=20)
	assert summary["totalEvents"] >= 1
	assert any(
		r["agent"] == "knowledge_validation" for r in summary.get("recent", [])
	)
