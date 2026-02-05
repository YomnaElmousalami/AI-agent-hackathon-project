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
			(customer_id, "Alex", 16, "CA", "Honda Accord", "Full Coverage"),
		)


def test_prepare_claim_packet_lists_missing_when_incomplete(temp_db):
	seed_customer(temp_db, 1)
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]

	res = insurance_mcp.prepare_claim_packet_impl(report_id=report_id)
	assert res["status"] == "draft"
	assert "location" in res["missingItems"]
	assert "vehicles_drivable" in res["missingItems"]
	assert "evidence_urls" not in res["missingItems"]


def test_prepare_claim_packet_ready_when_complete(temp_db):
	seed_customer(temp_db, 1)
	report_id = insurance_mcp.start_accident_report_impl(customer_id=1)["reportId"]
	insurance_mcp.update_accident_report_impl(
		report_id=report_id,
		location="San Jose, CA",
		injured_count=0,
		vehicles_drivable=True,
	)

	res = insurance_mcp.prepare_claim_packet_impl(report_id=report_id)
	assert res["status"] == "ready"
	assert res["missingItems"] == []
	assert res["packet"]["accident"]["location"] == "San Jose, CA"
