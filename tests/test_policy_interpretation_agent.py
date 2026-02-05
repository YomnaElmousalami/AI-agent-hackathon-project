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


def seed_customer(db_path: str, customer_id: int = 1, coverage_type: str = "Liability"):
	with sqlite3.connect(db_path) as conn:
		conn.execute(
			"""
			INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?, '01/01/2026', '01/01/2026');
			""",
			(customer_id, "Alex", 16, "CA", "Honda Accord", coverage_type),
		)


def test_interpret_policy_liability_only(temp_db):
	seed_customer(temp_db, 1, "Liability")
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]
	res = insurance_mcp.interpret_policy_impl(report_id=report_id)
	assert "liability" in (res["summary"] or "").lower()
	assert res["estimatedOutOfPocket"] is None


def test_interpret_policy_full_coverage(temp_db):
	seed_customer(temp_db, 1, "Full Coverage")
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]
	res = insurance_mcp.interpret_policy_impl(report_id=report_id)
	assert "full" in (res["summary"] or "").lower()
	assert res["estimatedOutOfPocket"] == res["estimatedDeductible"]
