import sqlite3

from fastapi.testclient import TestClient

import api_server


def _ensure_customer(customer_id: int = 46) -> None:
	with sqlite3.connect(api_server.DB_PATH) as conn:
		conn.execute(
			"INSERT OR IGNORE INTO customers (id, name, age, state, vehicle_name, coverage_type) VALUES (?, ?, ?, ?, ?, ?);",
			(customer_id, "Alex", 16, "VA", "Honda Accord", "liability"),
		)


def test_resources_recommend_endpoint_returns_resources():
	client = TestClient(api_server.app)
	_ensure_customer(46)

	res = client.post(
		"/api/resources/recommend",
		json={"customer_id": 46, "topic": "deductible", "limit": 5},
	)
	assert res.status_code == 200
	data = res.json()
	assert data.get("ok") is True
	assert isinstance(data.get("resources"), list)
	assert len(data["resources"]) >= 1
	first = data["resources"][0]
	assert "title" in first
	assert "type" in first
