import sqlite3

from database.insurance_db import init_db
import insurance_mcp


def fetch_all(db_path: str, sql: str, params=()):
	conn = sqlite3.connect(db_path)
	try:
		cur = conn.cursor()
		cur.execute(sql, params)
		return cur.fetchall()
	finally:
		conn.close()


def test_quiz_attempt_is_persisted_and_allows_reattempts(tmp_path):
	db_path = str(tmp_path / "test.db")
	init_db(db_path)

	customer_id = 46
	insurance_mcp.create_customer_impl(
		customer_id=customer_id,
		name="Quiz User",
		email="quiz@example.com",
		phone="555",
		address="Somewhere",
		database_path=db_path,
	)
	insurance_mcp.create_curriculum_plan_impl(
		customer_id=customer_id,
		topic="Insurance Basics",
		difficulty="beginner",
		goal="learn",
		database_path=db_path,
	)

	a1 = insurance_mcp.start_knowledge_quiz_attempt_impl(
		customer_id=customer_id, questions_limit=10, database_path=db_path
	)
	assert a1["attemptId"]
	qs = insurance_mcp.get_knowledge_questions_impl(
		customer_id=customer_id, limit=3, database_path=db_path
	)
	insurance_mcp.record_knowledge_quiz_answer_impl(
		customer_id=customer_id,
		attempt_id=a1["attemptId"],
		question_id=qs[0]["id"],
		answer=qs[0].get("expected") or "A",
		database_path=db_path,
	)
	insurance_mcp.record_knowledge_quiz_answer_impl(
		customer_id=customer_id,
		attempt_id=a1["attemptId"],
		question_id=qs[1]["id"],
		answer=qs[1].get("expected") or "A",
		database_path=db_path,
	)
	insurance_mcp.record_knowledge_quiz_answer_impl(
		customer_id=customer_id,
		attempt_id=a1["attemptId"],
		question_id=qs[2]["id"],
		answer="definitely wrong",
		database_path=db_path,
	)

	a2 = insurance_mcp.start_knowledge_quiz_attempt_impl(
		customer_id=customer_id, questions_limit=10, database_path=db_path
	)
	assert a2["attemptId"] != a1["attemptId"]

	attempt_rows = fetch_all(
		db_path,
		"SELECT id, customer_id, plan_id, total_points, earned_points, questions_total, questions_answered "
		"FROM knowledge_quiz_attempts WHERE customer_id=? ORDER BY id",
		(customer_id,),
	)
	assert len(attempt_rows) == 2
	assert attempt_rows[0][2] is not None
	assert attempt_rows[1][2] is not None

	results_rows_a1 = fetch_all(
		db_path,
		"SELECT attempt_id, question_id, correct, earned_points FROM knowledge_quiz_results WHERE attempt_id=?",
		(a1["attemptId"],),
	)
	assert len(results_rows_a1) == 3
	assert sum(r[2] for r in results_rows_a1) == 2  
	assert sum(float(r[3]) for r in results_rows_a1) > 0.0

	updated_attempt = fetch_all(
		db_path,
		"SELECT questions_answered, earned_points, total_points FROM knowledge_quiz_attempts WHERE id=?",
		(a1["attemptId"],),
	)[0]
	assert updated_attempt[0] == 3
	assert float(updated_attempt[2]) > 0.0
