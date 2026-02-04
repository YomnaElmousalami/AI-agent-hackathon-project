import os
import re
import sqlite3
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import insurance_mcp


DB_PATH = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))


app = FastAPI(title="Insurance AI-Agent API")

app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:3000",
		"http://127.0.0.1:3000",
		"http://localhost:3001",
		"http://127.0.0.1:3001",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class OnboardRequest(BaseModel):
	message: str


class CurriculumRequest(BaseModel):
	customer_id: int


def _parse_onboarding_sentence(message: str) -> dict[str, Any]:
	"""Parse a sentence like:
	"Hey. My id is 2, my name is Samuel, I'm 16, I live in NY, my vehicle is a Toyota Camry, and my coverage type is full coverage."

	This is intentionally simple/deterministic (no LLM), so the frontend works reliably.
	"""

	text = (message or "").strip()
	if not text:
		raise ValueError("message is empty")


	m_id = re.search(r"\b(?:id\s*(?:is)?\s*)(\d+)\b", text, re.IGNORECASE)
	if not m_id:
		m_id = re.search(r"\b(\d+)\b", text)
	if not m_id:
		raise ValueError("Couldn't find an id (number) in the message")
	customer_id = int(m_id.group(1))

	m_age = re.search(r"\b(?:i\s*['’]?m|i\s*am|age\s*(?:is)?)\s*(\d{1,3})\b", text, re.IGNORECASE)
	if not m_age:
		raise ValueError("Couldn't find an age in the message")
	age = int(m_age.group(1))

	m_state = re.search(r"\b(?:live\s*in|i\s*live\s*in|state\s*(?:is)?)\s*([A-Za-z]{2})\b", text, re.IGNORECASE)
	if not m_state:
		raise ValueError("Couldn't find a 2-letter state code (e.g. VA, NY)")
	state = m_state.group(1).upper()

	m_name = re.search(r"\bmy\s*name\s*is\s*([^,\.]+)", text, re.IGNORECASE)
	if not m_name:
		raise ValueError("Couldn't find 'my name is ...'")
	name = m_name.group(1).strip()

	m_vehicle = re.search(r"\b(?:vehicle\s*(?:is)?|car\s*(?:is)?)\s*(?:a\s+|an\s+)?([^,\.]+)", text, re.IGNORECASE)
	if not m_vehicle:
		raise ValueError("Couldn't find 'my vehicle is ...'")
	vehicle = m_vehicle.group(1).strip()

	m_cov = re.search(r"\bcoverage\s*(?:type\s*)?is\s*([^,\.]+)", text, re.IGNORECASE)
	if not m_cov:
		raise ValueError("Couldn't find 'coverage type is ...'")
	coverage = m_cov.group(1).strip()

	return {
		"id": customer_id,
		"name": name,
		"age": age,
		"state": state,
		"vehicleName": vehicle,
		"coverageType": coverage,
	}


@app.post("/api/onboard")
def onboard(req: OnboardRequest):
	try:
		parsed = _parse_onboarding_sentence(req.message)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# NOTE: `insurance_mcp.get_customer_info` is an MCP tool wrapper. For non-MCP callers
	# we call the underlying implementation.
	try:
		result = insurance_mcp.get_customer_info_impl(
			id=int(parsed["id"]),
			name=str(parsed["name"]),
			age=int(parsed["age"]),
			state=str(parsed["state"]),
			vehicleName=str(parsed["vehicleName"]),
			coverageType=str(parsed["coverageType"]),
		)
	except AttributeError:
		# Backward-compatible fallback, if impl isn't present for some reason.
		result = insurance_mcp.get_customer_info(
			id=int(parsed["id"]),
			name=str(parsed["name"]),
			age=int(parsed["age"]),
			state=str(parsed["state"]),
			vehicleName=str(parsed["vehicleName"]),
			coverageType=str(parsed["coverageType"]),
		)

	return {"ok": True, "parsed": parsed, "saved": result}


@app.get("/api/health")
def health():
	return {"ok": True, "db": DB_PATH}


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: int):
	"""Fetch an existing customer profile if it exists.

	Used by the frontend to display "already exists" instead of "saved".
	"""
	with sqlite3.connect(DB_PATH) as conn:
		conn.row_factory = sqlite3.Row
		row = conn.execute(
			"SELECT id, name, age, state, vehicle_name, coverage_type FROM customers WHERE id = ?;",
			(int(customer_id),),
		).fetchone()

	if row is None:
		raise HTTPException(status_code=404, detail="Customer not found")

	return {
		"ok": True,
		"customer": {
			"id": row["id"],
			"name": row["name"],
			"age": row["age"],
			"state": row["state"],
			"vehicleName": row["vehicle_name"],
			"coverageType": row["coverage_type"],
		},
	}


@app.post("/api/curriculum/plan")
def plan_curriculum(req: CurriculumRequest):
	"""Create/persist a curriculum plan (tool equivalent: plan_curriculum)."""
	try:
		# NOTE: `insurance_mcp.plan_curriculum` is an MCP tool wrapper. For non-MCP callers
		# we call the underlying implementation.
		try:
			plan = insurance_mcp.plan_curriculum_impl(int(req.customer_id))
		except AttributeError:
			plan = insurance_mcp.plan_curriculum(int(req.customer_id))
		return {"ok": True, "customerId": int(req.customer_id), "curriculum": plan}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/curriculum/{customer_id}")
def show_curriculum(customer_id: int):
	"""Get a persisted curriculum plan (impl equivalent: get_curriculum_impl)."""
	try:
		curriculum = insurance_mcp.get_curriculum_impl(int(customer_id))
		return {"ok": True, "customerId": int(customer_id), "curriculum": curriculum}
	except ValueError as e:
		# Mirror CLI behavior: show returns 'no curriculum' if missing
		raise HTTPException(status_code=404, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
