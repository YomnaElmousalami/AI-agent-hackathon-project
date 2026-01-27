import os
import re
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import insurance_mcp


app = FastAPI(title="Insurance AI-Agent API")

# For local dev, allow Vite dev server to call this API.
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:3000",
		"http://127.0.0.1:3000",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class OnboardRequest(BaseModel):
	message: str


def _parse_onboarding_sentence(message: str) -> dict[str, Any]:
	"""Parse a sentence like:
	"Hey. My id is 2, my name is Samuel, I'm 16, I live in NY, my vehicle is a Toyota Camry, and my coverage type is full coverage."

	This is intentionally simple/deterministic (no LLM), so the frontend works reliably.
	"""

	text = (message or "").strip()
	if not text:
		raise ValueError("message is empty")

	# id
	m_id = re.search(r"\b(?:id\s*(?:is)?\s*)(\d+)\b", text, re.IGNORECASE)
	if not m_id:
		# fallback: first number
		m_id = re.search(r"\b(\d+)\b", text)
	if not m_id:
		raise ValueError("Couldn't find an id (number) in the message")
	customer_id = int(m_id.group(1))

	# age
	m_age = re.search(r"\b(?:i\s*['’]?m|i\s*am|age\s*(?:is)?)\s*(\d{1,3})\b", text, re.IGNORECASE)
	if not m_age:
		raise ValueError("Couldn't find an age in the message")
	age = int(m_age.group(1))

	# state (2-letter)
	m_state = re.search(r"\b(?:live\s*in|i\s*live\s*in|state\s*(?:is)?)\s*([A-Za-z]{2})\b", text, re.IGNORECASE)
	if not m_state:
		raise ValueError("Couldn't find a 2-letter state code (e.g. VA, NY)")
	state = m_state.group(1).upper()

	# name
	m_name = re.search(r"\bmy\s*name\s*is\s*([^,\.]+)", text, re.IGNORECASE)
	if not m_name:
		raise ValueError("Couldn't find 'my name is ...'")
	name = m_name.group(1).strip()

	# vehicle
	m_vehicle = re.search(r"\b(?:vehicle\s*(?:is)?|car\s*(?:is)?)\s*(?:a\s+|an\s+)?([^,\.]+)", text, re.IGNORECASE)
	if not m_vehicle:
		raise ValueError("Couldn't find 'my vehicle is ...'")
	vehicle = m_vehicle.group(1).strip()

	# coverage
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
	return {"ok": True, "db": os.getenv("INSURANCE_DB_PATH", "database/insurance.db")}
