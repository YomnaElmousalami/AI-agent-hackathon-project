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


def seed_customer(db_path: str, customer_id: int = 1, state: str = "CA"):
	with sqlite3.connect(db_path) as conn:
		conn.execute(
			"""
			INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?, '01/01/2026', '01/01/2026');
			""",
			(customer_id, "Alex", 16, state, "Honda Accord", "Liability"),
		)


def test_recommend_resources_returns_items_and_saves(temp_db):
	seed_customer(temp_db, 1, "CA")
	resources = insurance_mcp.recommend_resources_impl(customer_id=1, topic="deductible", limit=5)
	assert isinstance(resources, list)
	assert len(resources) >= 1
	assert resources[0].get("title") in ("No verified resource found.", "No resource found.")

	with sqlite3.connect(temp_db) as conn:
		row = conn.execute("SELECT COUNT(*) FROM recommended_resources WHERE customer_id = 1;").fetchone()
	assert row[0] >= 1
