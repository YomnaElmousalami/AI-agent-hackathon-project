"""Tiny smoke test: POST a profile to the API and verify it was written to SQLite.

Run this while the API is up:
  python .\\smoke_save_profile.py

It will:
- POST to /api/profile
- Check the `customers` table for that id

This avoids needing Postman while you iterate on the UI.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.request

API = os.getenv("API", "http://127.0.0.1:8001")
DB_PATH = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))

payload = {
    "id": 999,
    "name": "Test User",
    "age": 16,
    "state": "VA",
    "vehicleName": "Honda Accord",
    "coverageType": "liability",
}

req = urllib.request.Request(
    f"{API}/api/profile",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

print("POST", req.full_url)
print("Payload:", payload)

try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read().decode("utf-8")
        print("Response:", body)
except Exception as e:
    raise SystemExit(f"API call failed: {e}")

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, name, age, state, vehicle_name, coverage_type FROM customers WHERE id = ?;",
        (payload["id"],),
    ).fetchone()

if not row:
    raise SystemExit("DB check failed: customer row not found")

print("DB row:", dict(row))
print("OK")
