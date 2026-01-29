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


def _seed_customer(db_path: str, customer_id: int = 1, coverage_type: str = "Full Coverage"):
	with sqlite3.connect(db_path) as conn:
		conn.execute(
			"""
			INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?, '01/01/2026', '01/01/2026');
			""",
			(customer_id, "Alex", 16, "CA", "Honda Accord", coverage_type),
		)


def test_generate_action_plan_has_steps(temp_db):
	_seed_customer(temp_db, 1)
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]
	insurance_mcp.update_accident_report_impl(
		report_id=report_id,
		location="San Jose",
		injured_count=0,
		vehicles_drivable=False,
		evidence_urls=["https://example.com/p.jpg"],
	)

	insurance_mcp.assess_accident_severity_impl(report_id=report_id)
	insurance_mcp.interpret_policy_impl(report_id=report_id)

	plan = insurance_mcp.generate_action_plan_impl(report_id=report_id)
	assert plan["reportId"] == report_id
	assert len(plan["steps"]) >= 3
	assert any("Notify" in s["step"] or "insurer" in s["step"].lower() for s in plan["steps"])
