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


def test_severity_emergency_when_injuries(temp_db):
	_seed_customer(temp_db, 1)
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]
	insurance_mcp.update_accident_report_impl(report_id=report_id, injured_count=1, vehicles_drivable=True)

	res = insurance_mcp.assess_accident_severity_impl(report_id=report_id)
	assert res["severity"] == "high"
	assert res["urgency"] == "emergency"


def test_severity_medium_when_not_drivable(temp_db):
	_seed_customer(temp_db, 1)
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]
	insurance_mcp.update_accident_report_impl(report_id=report_id, injured_count=0, vehicles_drivable=False)

	res = insurance_mcp.assess_accident_severity_impl(report_id=report_id)
	assert res["severity"] == "medium"
	assert res["urgency"] == "soon"
