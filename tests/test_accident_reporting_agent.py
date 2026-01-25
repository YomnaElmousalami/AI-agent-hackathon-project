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
			(customer_id, "Alex", 16, "CA", "Honda Accord", "Full Coverage"),
		)


def test_accident_report_create_update_finalize(temp_db):
	_seed_customer(temp_db, 1)

	created = insurance_mcp.start_accident_report_impl(customer_id=1)
	report_id = created["reportId"]
	assert report_id
	assert created["status"] == "collecting"

	updated = insurance_mcp.update_accident_report_impl(
		report_id=report_id,
		location="San Jose, CA",
		injured_count=0,
		vehicles_drivable=False,
		evidence_urls=["https://example.com/photo1.jpg"],
		notes="rear-end accident",
	)
	assert updated["location"] == "San Jose, CA"
	assert updated["injuredCount"] == 0
	assert updated["vehiclesDrivable"] is False
	assert "photo1" in (updated["evidenceUrls"][0] or "")

	fin = insurance_mcp.finalize_accident_report_impl(report_id=report_id)
	assert fin["status"] == "ready"
