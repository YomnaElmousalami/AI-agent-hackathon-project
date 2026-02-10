import os
import asyncio
import shutil
import subprocess
from pathlib import Path
import re
import sqlite3
from typing import Any
import urllib.parse
import urllib.request
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import insurance_mcp

# NOTE: The FastAPI backend is used for deterministic endpoints (curriculum, knowledge quiz, etc.).
# Some environments (notably Python 3.14+) may have incompatibilities with LangChain dependencies.
# We keep the API server runnable by making teacher-agent helpers optional at import time.
try:
	from langchain.teacher_agent import build_khan_style_lesson, render_lesson_script  # type: ignore
except Exception:  # pragma: no cover
	build_khan_style_lesson = None  # type: ignore
	render_lesson_script = None  # type: ignore

try:
	import langchain.user_onboarding_agent as user_onboarding_agent  # type: ignore
except Exception:  # pragma: no cover
	user_onboarding_agent = None  # type: ignore

try:
	import langchain.curriculum_planner_agent as curriculum_planner_agent  # type: ignore
except Exception:  # pragma: no cover
	curriculum_planner_agent = None  # type: ignore

try:
	import langchain.policy_interpretation_agent as policy_interpretation_agent  # type: ignore
except Exception:  # pragma: no cover
	policy_interpretation_agent = None  # type: ignore

try:
	import langchain.claims_preparation_agent as claims_preparation_agent  # type: ignore
except Exception:  # pragma: no cover
	claims_preparation_agent = None  # type: ignore

try:
	import langchain.action_plan_agent as action_plan_agent  # type: ignore
except Exception:  # pragma: no cover
	action_plan_agent = None  # type: ignore

try:
	import langchain.escalation_and_routing_agent as escalation_and_routing_agent  # type: ignore
except Exception:  # pragma: no cover
	escalation_and_routing_agent = None  # type: ignore


DB_PATH = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", os.path.join("generated_media"))).resolve()


app = FastAPI(title="Insurance AI-Agent API")

MEDIA_DIR.mkdir(parents=True, exist_ok=True)

try:
	from fastapi.staticfiles import StaticFiles
	app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
except Exception:
	pass

app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:3000",
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


class TeacherLessonRequest(BaseModel):
	customer_id: int
	module_order: int


class TeacherVideoRequest(BaseModel):
	customer_id: int
	module_order: int
	# Optional: let the caller freeze an id so they can re-fetch it.
	video_id: str | None = None


class TeacherYoutubeRequest(BaseModel):
	customer_id: int
	module_order: int


class TeacherVimeoRequest(BaseModel):
	customer_id: int
	module_order: int


class TeacherEmbeddedVideoRequest(BaseModel):
	customer_id: int
	module_order: int


class KnowledgeQuestionsRequest(BaseModel):
	customer_id: int
	limit: int = 10
	module_order: int | None = None
	# Optional: if provided, questions will be generated with a stable seed that
	# matches the attempt. This prevents "Unknown question_id" when answering.
	attempt_id: str | None = None


class KnowledgeStartAttemptRequest(BaseModel):
	customer_id: int
	questions_limit: int = 10
	module_order: int | None = None


class KnowledgeAnswerRequest(BaseModel):
	customer_id: int
	attempt_id: str
	question_id: str
	answer: str


class KnowledgeModuleViewRequest(BaseModel):
	customer_id: int
	module_order: int


class ResourceRecommendRequest(BaseModel):
	customer_id: int
	topic: str
	state: str | None = None
	limit: int = 8


class ResourceSummarizeRequest(BaseModel):
	resources: list[dict]
	style: str = "general"


# ---------------------------
# Accident / Claims agent APIs
# ---------------------------


class StartAccidentReportRequest(BaseModel):
	customer_id: int


class UpdateAccidentReportRequest(BaseModel):
	report_id: str
	location: str | None = None
	injured_count: int | None = None
	vehicles_drivable: bool | None = None
	evidence_urls: list[str] | None = None
	notes: str | None = None


class ReportIdRequest(BaseModel):
	report_id: str

def parse_onboarding_sentence(message: str) -> dict[str, Any]:
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

	# NOTE: Avoid unbounded backtracking here (these patterns are used on arbitrary user text).
	# Keep captures short and stop at common separators.
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


async def _run_onboarding_llm(message: str) -> tuple[str | None, str | None]:
	"""Run the LangGraph onboarding agent and return its final text (if any)."""

	if user_onboarding_agent is None:
		return None, "onboarding_agent_unavailable"

	try:
		agent = await user_onboarding_agent.initialize_agent()
		text = await asyncio.wait_for(
			user_onboarding_agent.run_agent(agent, message),
			timeout=60,
		)
		return text, None
	except Exception as e:
		return None, str(e)


async def _call_llm(fn, *args, **kwargs) -> tuple[str | None, str | None]:
	if fn is None:
		return None, "agent_unavailable"
	try:
		text = await fn(*args, **kwargs)
		return text, None
	except Exception as e:
		return None, str(e)


def _run_llm_sync(fn, *args, **kwargs) -> tuple[str | None, str | None]:
	try:
		return asyncio.run(_call_llm(fn, *args, **kwargs))
	except RuntimeError:
		return None, "event_loop_running"
	except Exception as e:
		return None, str(e)


@app.post("/api/onboard")
def onboard(req: OnboardRequest):
	try:
		parsed = parse_onboarding_sentence(req.message)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

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
		result = insurance_mcp.get_customer_info(
			id=int(parsed["id"]),
			name=str(parsed["name"]),
			age=int(parsed["age"]),
			state=str(parsed["state"]),
			vehicleName=str(parsed["vehicleName"]),
			coverageType=str(parsed["coverageType"]),
		)

	llm_response = None
	llm_error = None
	try:
		llm_response, llm_error = asyncio.run(_run_onboarding_llm(req.message))
	except RuntimeError:
		# Event loop already running (unlikely in sync FastAPI handler); skip LLM.
		llm_response = None
		llm_error = "event_loop_running"

	return {
		"ok": True,
		"parsed": parsed,
		"saved": result,
		"llmResponse": llm_response,
		"llmError": llm_error,
	}


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
		try:
			plan = insurance_mcp.plan_curriculum_impl(int(req.customer_id))
		except AttributeError:
			plan = insurance_mcp.plan_curriculum(int(req.customer_id))

		llm_response, llm_error = _run_llm_sync(
			getattr(curriculum_planner_agent, "run_llm", None),
			int(req.customer_id),
			action="plan",
		)

		return {
			"ok": True,
			"customerId": int(req.customer_id),
			"curriculum": plan,
			"llmResponse": llm_response,
			"llmError": llm_error,
		}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/curriculum/{customer_id}")
def show_curriculum(customer_id: int):
	"""Get a persisted curriculum plan (impl equivalent: get_curriculum_impl)."""
	try:
		curriculum = insurance_mcp.get_curriculum_impl(int(customer_id))
		llm_response, llm_error = _run_llm_sync(
			getattr(curriculum_planner_agent, "run_llm", None),
			int(customer_id),
			action="show",
		)
		return {
			"ok": True,
			"customerId": int(customer_id),
			"curriculum": curriculum,
			"llmResponse": llm_response,
			"llmError": llm_error,
		}
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/questions")
def knowledge_questions(req: KnowledgeQuestionsRequest):
	"""Return knowledge validation questions for a customer (optionally for a single module)."""
	try:
		seed: str | None = str(req.attempt_id) if req.attempt_id else None
		# If caller didn't pass attempt_id, try to find the most recent attempt for
		# this customer/module and use it as the seed.
		if seed is None:
			with sqlite3.connect(DB_PATH) as conn:
				conn.row_factory = sqlite3.Row
				row = conn.execute(
					"""
					SELECT id
					FROM knowledge_quiz_attempts
					WHERE customer_id = ?
					  AND (? IS NULL OR module_order = ?)
					ORDER BY rowid DESC
					LIMIT 1;
					""",
					(
						int(req.customer_id),
						int(req.module_order) if req.module_order is not None else None,
						int(req.module_order) if req.module_order is not None else None,
					),
				).fetchone()
				if row is not None:
					seed = str(row["id"])

		qs = insurance_mcp.get_knowledge_questions_impl(
			customer_id=int(req.customer_id),
			limit=int(req.limit),
			module_order=int(req.module_order) if req.module_order is not None else None,
			mode="generated",
			seed=seed,
		)
		return {"ok": True, "customerId": int(req.customer_id), "questions": qs}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/attempts/start")
def knowledge_start_attempt(req: KnowledgeStartAttemptRequest):
	"""Start a persisted knowledge quiz attempt (saves attempt + can be re-attempted)."""
	try:
		attempt = insurance_mcp.start_knowledge_quiz_attempt_impl(
			customer_id=int(req.customer_id),
			questions_limit=int(req.questions_limit),
			module_order=int(req.module_order) if req.module_order is not None else None,
		)
		return {"ok": True, **attempt}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/attempts/answer")
def knowledge_record_answer(req: KnowledgeAnswerRequest):
	"""Grade + persist one answer for a given knowledge attempt."""
	try:
		graded = insurance_mcp.record_knowledge_quiz_answer_impl(
			customer_id=int(req.customer_id),
			attempt_id=str(req.attempt_id),
			question_id=str(req.question_id),
			answer=str(req.answer),
		)
		return {"ok": True, **graded}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/attempts/{customer_id}")
def knowledge_attempts(customer_id: int, limit: int = 20):
	"""List recent knowledge quiz attempts (history)."""
	try:
		attempts = insurance_mcp.get_knowledge_quiz_attempts_impl(customer_id=int(customer_id), limit=int(limit))
		return {"ok": True, "customerId": int(customer_id), "attempts": attempts}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/module_view")
def knowledge_record_module_view(req: KnowledgeModuleViewRequest):
	"""Persist that a customer opened a module in the Knowledge Validation flow."""
	try:
		row = insurance_mcp.record_knowledge_validation_module_view_impl(
			customer_id=int(req.customer_id),
			module_order=int(req.module_order),
		)
		return {"ok": True, "view": row}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resources/recommend")
def recommend_resources(req: ResourceRecommendRequest):
	"""Return curated, state-aware resource recommendations for a customer."""
	try:
		resources = insurance_mcp.recommend_resources_impl(
			customer_id=int(req.customer_id),
			topic=str(req.topic),
			state=str(req.state) if req.state else None,
			limit=int(req.limit),
		)
		return {"ok": True, "customerId": int(req.customer_id), "resources": resources}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resources/summarize")
def summarize_resources(req: ResourceSummarizeRequest):
	"""Summarize a list of resources into one paragraph (deterministic)."""
	try:
		summary = insurance_mcp.summarize_resources_impl(list(req.resources or []), style=str(req.style or "general"))
		return {"ok": True, **summary}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accident/report/start")
def accident_report_start(req: StartAccidentReportRequest):
	"""Accident Reporting Agent: create a new accident report (case)."""
	try:
		res = insurance_mcp.start_accident_report_impl(customer_id=int(req.customer_id))
		return {"ok": True, **res}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accident/report/update")
def accident_report_update(req: UpdateAccidentReportRequest):
	"""Accident Reporting Agent: update an existing accident report."""
	try:
		res = insurance_mcp.update_accident_report_impl(
			report_id=str(req.report_id),
			location=str(req.location) if req.location is not None else None,
			injured_count=int(req.injured_count) if req.injured_count is not None else None,
			vehicles_drivable=bool(req.vehicles_drivable) if req.vehicles_drivable is not None else None,
			evidence_urls=list(req.evidence_urls) if req.evidence_urls is not None else None,
			notes=str(req.notes) if req.notes is not None else None,
		)
		return {"ok": True, **res}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accident/report/finalize")
def accident_report_finalize(req: ReportIdRequest):
	"""Accident Reporting Agent: finalize report so downstream agents can run."""
	try:
		res = insurance_mcp.finalize_accident_report_impl(report_id=str(req.report_id))
		return {"ok": True, **res}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accident/severity")
def accident_severity(req: ReportIdRequest):
	"""Accident Severity Assessment Agent."""
	try:
		res = insurance_mcp.assess_accident_severity_impl(report_id=str(req.report_id))
		return {"ok": True, **res}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/policy/interpret")
def policy_interpret(req: ReportIdRequest):
	"""Policy Interpretation Agent."""
	try:
		res = insurance_mcp.interpret_policy_impl(report_id=str(req.report_id))
		llm_response, llm_error = _run_llm_sync(
			getattr(policy_interpretation_agent, "run_llm", None),
			str(req.report_id),
		)
		return {"ok": True, **res, "llmResponse": llm_response, "llmError": llm_error}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/claims/prepare")
def claims_prepare(req: ReportIdRequest):
	"""Claims Preparation Agent (prepare claim packet)."""
	try:
		res = insurance_mcp.prepare_claim_packet_impl(report_id=str(req.report_id))
		llm_response, llm_error = _run_llm_sync(
			getattr(claims_preparation_agent, "run_llm", None),
			str(req.report_id),
		)
		return {"ok": True, **res, "llmResponse": llm_response, "llmError": llm_error}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/action_plan")
def action_plan(req: ReportIdRequest):
	"""Action Plan Agent (generate next steps)."""
	try:
		res = insurance_mcp.generate_action_plan_impl(report_id=str(req.report_id))
		llm_response, llm_error = _run_llm_sync(
			getattr(action_plan_agent, "run_llm", None),
			str(req.report_id),
		)
		return {"ok": True, **res, "llmResponse": llm_response, "llmError": llm_error}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/escalation")
def escalation(req: ReportIdRequest):
	"""Escalation & Routing Agent (route to human vs emergency vs self-serve)."""
	try:
		res = insurance_mcp.escalate_and_route_impl(report_id=str(req.report_id))
		llm_response, llm_error = _run_llm_sync(
			getattr(escalation_and_routing_agent, "run_llm", None),
			str(req.report_id),
		)
		return {"ok": True, **res, "llmResponse": llm_response, "llmError": llm_error}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/teacher/lesson")
def teacher_lesson(req: TeacherLessonRequest):
	"""Generate a Khan-style lesson script for a specific curriculum module.

	This endpoint is intentionally deterministic (LLM-free) so the UI is stable.
	"""
	try:
		if build_khan_style_lesson is None or render_lesson_script is None:
			raise HTTPException(
				status_code=501,
				detail=(
					"Teacher lesson generation isn't available in this environment. "
					"(Optional LangChain dependencies failed to import.)"
				),
			)

		customer_id = int(req.customer_id)
		module_order = int(req.module_order)
		if customer_id <= 0:
			raise ValueError("customer_id must be positive")
		if module_order <= 0:
			raise ValueError("module_order must be positive")

		curriculum = insurance_mcp.get_curriculum_impl(customer_id)
		module = next(
			(m for m in curriculum if int(m.get("order")) == module_order),
			None,
		)
		if not module:
			raise HTTPException(status_code=404, detail="Module not found for this curriculum")

		try:
			insurance_mcp.record_teacher_module_view_impl(
				customer_id=customer_id,
				module_order=module_order,
				module_title=str(module.get("module")),
			)
		except Exception:
			pass

		age = 18
		with sqlite3.connect(DB_PATH) as conn:
			conn.row_factory = sqlite3.Row
			row = conn.execute("SELECT age FROM customers WHERE id = ?;", (customer_id,)).fetchone()
			if row is not None:
				age = int(row["age"])

		lesson = build_khan_style_lesson(
			module_title=str(module.get("module")),
			module_description=str(module.get("description")),
			age=age,
		)
		script = render_lesson_script(lesson)

		return {
			"ok": True,
			"customerId": customer_id,
			"moduleOrder": module_order,
			"moduleTitle": str(module.get("module")),
			"lesson": {
				"title": lesson.title,
				"objective": lesson.objective,
				"hook": lesson.hook,
				"keyPoints": list(lesson.key_points),
				"analogy": lesson.analogy,
				"workedExampleQ": lesson.worked_example_q,
				"workedExampleA": lesson.worked_example_a,
				"recap": lesson.recap,
				"script": script,
			},
		}
	except HTTPException:
		raise
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


def ensure_ffmpeg_available() -> None:
	"""Ensure the backend can find an ffmpeg executable.

	We primarily rely on PATH, but Windows winget installs often put ffmpeg
	under the WinGet Packages directory without updating the environment for an
	already-running server process.

	Support these discovery options:
	- FFMPEG_BIN env var (full path to ffmpeg.exe)
	- PATH lookup (shutil.which)
	- WinGet default install location (Gyan.FFmpeg)
	"""
	ff = os.getenv("FFMPEG_BIN")
	if ff and Path(ff).exists():
		return
	if shutil.which("ffmpeg") is not None:
		return
	
	local_appdata = os.getenv("LOCALAPPDATA")
	if local_appdata:
		winget_root = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
		try:
			if winget_root.exists():
				candidates = list(winget_root.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))
				if candidates:
					os.environ["FFMPEG_BIN"] = str(candidates[0])
					return
		except Exception:
			pass

	raise HTTPException(
		status_code=501,
		detail=(
			"Video generation requires ffmpeg, but it wasn't found. "
			"Install ffmpeg (Windows: winget install Gyan.FFmpeg) and restart the backend, "
			"or set FFMPEG_BIN to the full path of ffmpeg.exe."
		),
	)


def safe_filename(s: str) -> str:
	return re.sub(r"[^A-Za-z0-9._-]+", "_", (s or "").strip())[:120] or "lesson"


def render_lesson_to_mp4(*, title: str, script: str, out_path: Path) -> None:
	"""Create a simple MP4 using ffmpeg with burned-in text.

	This is intentionally basic: a dark background + centered text.
	"""
	ensure_ffmpeg_available()
	out_path = Path(out_path)
	out_path.parent.mkdir(parents=True, exist_ok=True)


	text = (title + "\n\n" + script).strip()
	if len(text) > 8000:
		text = text[:8000] + "\n..."

	text_file = out_path.with_suffix(".txt")
	text_file.write_text(text, encoding="utf-8")

	text_file_escaped = str(text_file).replace("\\", "\\\\").replace(":", "\\:")

	filter_expr = (
		"drawtext="
		"font='Arial':"
		"fontsize=28:"
		"fontcolor=white:"
		"x=(w-text_w)/2:"
		"y=(h-text_h)/2:"
		"line_spacing=10:"
		"textfile='%s':"
		"reload=0" % text_file_escaped
	)

	ffmpeg_exe = os.getenv("FFMPEG_BIN")
	cmd = [
		ffmpeg_exe or "ffmpeg",
		"-y",
		"-f",
		"lavfi",
		"-i",
		"color=c=#111111:s=1280x720:d=12",
		"-vf",
		filter_expr,
		"-c:v",
		"libx264",
		"-pix_fmt",
		"yuv420p",
		out_path.as_posix() if os.name != "nt" else str(out_path),
	]

	proc = subprocess.run(cmd, capture_output=True, text=True)
	if proc.returncode != 0:
		raise HTTPException(
			status_code=500,
			detail=(
				"ffmpeg failed to generate the video. "
				+ (proc.stderr.strip()[-1200:] if proc.stderr else "")
			),
		)


@app.post("/api/teacher/video")
def teacher_video(req: TeacherVideoRequest):
	"""Generate an actual MP4 for a lesson module and return a playable URL."""
	try:
		customer_id = int(req.customer_id)
		module_order = int(req.module_order)
		if customer_id <= 0:
			raise ValueError("customer_id must be positive")
		if module_order <= 0:
			raise ValueError("module_order must be positive")

		curriculum = insurance_mcp.get_curriculum_impl(customer_id)
		module = next(
			(m for m in curriculum if int(m.get("order")) == module_order),
			None,
		)
		if not module:
			raise HTTPException(status_code=404, detail="Module not found for this curriculum")

		age = 18
		with sqlite3.connect(DB_PATH) as conn:
			conn.row_factory = sqlite3.Row
			row = conn.execute("SELECT age FROM customers WHERE id = ?;", (customer_id,)).fetchone()
			if row is not None:
				age = int(row["age"])

		lesson = build_khan_style_lesson(
			module_title=str(module.get("module")),
			module_description=str(module.get("description")),
			age=age,
		)
		script = render_lesson_script(lesson)

		video_id = req.video_id or f"c{customer_id}_m{module_order}"
		base = safe_filename(video_id + "_" + str(module.get("module")))
		out_path = MEDIA_DIR / f"{base}.mp4"

		if not out_path.exists():
			render_lesson_to_mp4(title=str(lesson.title), script=str(script), out_path=out_path)

		return {
			"ok": True,
			"videoId": str(video_id),
			"customerId": customer_id,
			"moduleOrder": module_order,
			"moduleTitle": str(module.get("module")),
			"url": f"/media/{out_path.name}",
		}
	except HTTPException:
		raise
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/teacher/embedded_video")
def teacher_embedded_video(req: TeacherEmbeddedVideoRequest):
	"""Return a *guaranteed playable* embedded video URL for a module.

	Third-party platforms (YouTube/Vimeo) can block iframe embeds unpredictably.
	This endpoint always returns a URL served by this API under /media.

	Strategy:
	- If a pre-generated video exists for this module, use it.
	- Otherwise, generate a simple MP4 via ffmpeg (if available).
	"""
	try:
		customer_id = int(req.customer_id)
		module_order = int(req.module_order)
		if customer_id <= 0:
			raise ValueError("customer_id must be positive")
		if module_order <= 0:
			raise ValueError("module_order must be positive")

		curriculum = insurance_mcp.get_curriculum_impl(customer_id)
		module = next((m for m in curriculum if int(m.get("order")) == module_order), None)
		if not module:
			raise HTTPException(status_code=404, detail="Module not found for this curriculum")


		video_id = f"c{customer_id}_m{module_order}"
		base = safe_filename(video_id + "_" + str(module.get("module")))
		out_path = MEDIA_DIR / f"{base}.mp4"

		if not out_path.exists():
			age = 18
			with sqlite3.connect(DB_PATH) as conn:
				conn.row_factory = sqlite3.Row
				row = conn.execute("SELECT age FROM customers WHERE id = ?;", (customer_id,)).fetchone()
				if row is not None:
					age = int(row["age"])

			lesson = build_khan_style_lesson(
				module_title=str(module.get("module")),
				module_description=str(module.get("description")),
				age=age,
			)
			script = render_lesson_script(lesson)
			render_lesson_to_mp4(title=str(lesson.title), script=str(script), out_path=out_path)

		return {
			"ok": True,
			"provider": "self",
			"customerId": customer_id,
			"moduleOrder": module_order,
			"moduleTitle": str(module.get("module")),
			"embedUrl": f"/media/{out_path.name}",
			"mime": "video/mp4",
		}
	except HTTPException:
		raise
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


def youtube_search_url(query: str) -> str:
	q = (query or "").strip() or "insurance basics"
	return "https://www.youtube.com/results?search_query=" + re.sub(r"\s+", "+", q)


def youtube_embed_search_url(query: str) -> str:
	"""Return an embeddable YouTube URL that plays search results.

	This avoids relying on a specific video id that may become unavailable.
	"""
	q = (query or "").strip() or "insurance basics"
	q = re.sub(r"\s+", "+", q)

	return f"https://www.youtube-nocookie.com/embed?listType=search&list={q}&rel=0&modestbranding=1"


def youtube_api_key() -> str | None:
	return os.getenv("YOUTUBE_API_KEY")


def youtube_embed_for_video_id(video_id: str) -> str:
	vid = (video_id or "").strip()
	if not vid:
		return ""
	return f"https://www.youtube-nocookie.com/embed/{vid}?rel=0&modestbranding=1"


def vimeo_embed_for_video_id(video_id: str) -> str:
	vid = (video_id or "").strip()
	if not vid:
		return ""

	return f"https://player.vimeo.com/video/{vid}?dnt=1"


def curated_vimeo_videos_for_topic(topic: str) -> list[dict[str, str]]:
	"""Best-effort curated Vimeo videos for common insurance topics.

	Why curated:
	- Vimeo search without an API key is not reliable.
	- We want a demo that always has *some* embeddable video.

	Notes:
	- Vimeo IDs can still disappear over time, but this is typically more stable
	  than random YouTube embeds without API verification.
	"""

	t = (topic or "").strip().lower()
	if not t:
		return []


	curated: dict[str, list[str]] = {
		"insurance": ["76979871"],
		"auto": ["76979871"],
		"coverage": ["76979871"],
	}

	matched_ids: list[str] = []
	for k, ids in curated.items():
		if k in t:
			matched_ids = ids
			break
	if not matched_ids:
		matched_ids = curated.get("insurance", [])

	results: list[dict[str, str]] = []
	for vid in matched_ids:
		if not vid:
			continue
		results.append(
			{
				"videoId": vid,
				"title": "",
				"channelTitle": "",
				"url": f"https://vimeo.com/{vid}",
				"embedUrl": vimeo_embed_for_video_id(vid),
			}
		)
	return results


@app.post("/api/teacher/vimeo")
def teacher_vimeo(req: TeacherVimeoRequest):
	"""Return a Vimeo embed URL for a module.

	This is intended as a more reliable embedded-video fallback when YouTube
	embeds are unavailable and no YouTube API key is configured.
	"""
	try:
		customer_id = int(req.customer_id)
		module_order = int(req.module_order)
		if customer_id <= 0:
			raise ValueError("customer_id must be positive")
		if module_order <= 0:
			raise ValueError("module_order must be positive")

		curriculum = insurance_mcp.get_curriculum_impl(customer_id)
		module = next((m for m in curriculum if int(m.get("order")) == module_order), None)
		if not module:
			raise HTTPException(status_code=404, detail="Module not found for this curriculum")

		module_title = str(module.get("module") or "")
		module_desc = str(module.get("description") or "")
		query = (module_title + " " + module_desc).strip()

		videos = curated_vimeo_videos_for_topic(module_title) or curated_vimeo_videos_for_topic(query)
		embed_candidates = [v.get("embedUrl") for v in videos if v.get("embedUrl")]
		if not embed_candidates:
			raise HTTPException(status_code=500, detail="No Vimeo embed candidates available")

		return {
			"ok": True,
			"customerId": customer_id,
			"moduleOrder": module_order,
			"moduleTitle": module_title,
			"query": query,
			"embedUrl": embed_candidates[0],
			"embedCandidates": embed_candidates,
			"videos": videos,
		}
	except HTTPException:
		raise
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


def curated_youtube_videos_for_topic(topic: str) -> list[dict[str, str]]:
	"""Return a small list of known embeddable videos for common insurance topics.

	Why this exists:
	- Demos shouldn't hard-fail if the YouTube Data API key isn't configured.
	- A curated list gives us a stable, watchable default.

	Notes:
	- These are best-effort. Videos can still disappear over time.
	- If nothing matches, return an empty list and the caller can fall back to
	  the embeddable search playlist.
	"""

	t = (topic or "").strip().lower()
	if not t:
		return []

	def ytid(url_or_id: str) -> str:
		"""Extract a YouTube video id from a URL (watch?v= / youtu.be / embed) or return the id."""
		s = (url_or_id or "").strip()
		if not s:
			return ""
		# If caller passed a raw 11-char id, keep it.
		m = re.search(r"\b([A-Za-z0-9_-]{11})\b", s)
		if not m:
			return ""
		# Prefer explicit v=... when present.
		mv = re.search(r"(?:\?|&)v=([A-Za-z0-9_-]{11})\b", s)
		if mv:
			return mv.group(1)
		# Prefer youtu.be/<id>
		ms = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})\b", s)
		if ms:
			return ms.group(1)
		# Prefer /embed/<id>
		me = re.search(r"/embed/([A-Za-z0-9_-]{11})\b", s)
		if me:
			return me.group(1)
		# Otherwise, accept the first 11-char candidate.
		return m.group(1)

	curated: dict[str, list[str]] = {
		# --- General foundations ---
		"what is car insurance": [ytid("https://www.youtube.com/watch?v=q6ztnQLLZkg&t=372s")],
		"car insurance": [ytid("https://www.youtube.com/watch?v=q6ztnQLLZkg&t=372s")],
		"auto insurance": [ytid("https://www.youtube.com/watch?v=q6ztnQLLZkg&t=372s")],
		"what is insurance": [ytid("https://www.youtube.com/watch?v=q6ztnQLLZkg&t=372s")],

		# --- Core policy mechanics ---
		"deductible": [ytid("https://www.youtube.com/watch?v=UoPN84v2KrU&t=3s")],
		"deductibles": [ytid("https://www.youtube.com/watch?v=UoPN84v2KrU&t=3s")],
		"premium": [ytid("https://www.youtube.com/watch?v=Ly3tiv7f4Hg")],
		"claim": [ytid("https://www.youtube.com/watch?v=S-I6ZLrF3oQ")],
		"how to file a claim": [ytid("https://www.youtube.com/watch?v=lsq4hD6kg8o")],
		"file a claim": [ytid("https://www.youtube.com/watch?v=lsq4hD6kg8o")],
		"coverage": [ytid("https://www.youtube.com/watch?v=iAXvv9BM-3U")],
		"types of coverage for auto insurance": [ytid("https://www.youtube.com/watch?v=g8uMWX1JcC4")],
		"types of coverage": [ytid("https://www.youtube.com/watch?v=g8uMWX1JcC4")],
		"liability": [ytid("https://www.youtube.com/watch?v=sulcwnaHAvI")],
		"comprehensive": [ytid("https://www.youtube.com/watch?v=lMcxwBLOpjs")],
		"collision": [ytid("https://www.youtube.com/watch?v=lMcxwBLOpjs")],
		"endorsement": [ytid("https://www.youtube.com/watch?v=am8XBrdFHfU")],
		"endorsements": [ytid("https://www.youtube.com/watch?v=am8XBrdFHfU")],
		"how to read your insurance policy": [ytid("https://www.youtube.com/watch?v=NYwZVxYe8QU")],
		"read your insurance policy": [ytid("https://www.youtube.com/watch?v=NYwZVxYe8QU")],
		"read your policy": [ytid("https://www.youtube.com/watch?v=NYwZVxYe8QU")],
		"insurance policy": [ytid("https://www.youtube.com/watch?v=NYwZVxYe8QU")],
		"how to choose the right insurance plan": [ytid("https://www.youtube.com/watch?v=LWDPRx3k4-8")],
		"choose the right insurance plan": [ytid("https://www.youtube.com/watch?v=LWDPRx3k4-8")],
		"bundling": [ytid("https://www.youtube.com/watch?v=M_tpraTiJMk")],
		"bundle": [ytid("https://www.youtube.com/watch?v=M_tpraTiJMk")],
		"no-fault": [ytid("https://www.youtube.com/watch?v=stdqM-OTmyk")],
		"rental": [ytid("https://www.youtube.com/watch?v=s6LcnFEqQxY")],
		"rental car": [ytid("https://www.youtube.com/watch?v=s6LcnFEqQxY")],
		"rental car coverage": [ytid("https://www.youtube.com/watch?v=s6LcnFEqQxY")],
		"uninsured": [ytid("https://www.youtube.com/watch?v=jcuN4jDCE3M")],
		"uninsured motorist": [ytid("https://www.youtube.com/watch?v=jcuN4jDCE3M")],
		"uninsured motorist situations": [ytid("https://www.youtube.com/watch?v=jcuN4jDCE3M")],
		"total loss": [ytid("https://www.youtube.com/watch?v=Ynbgf5uda7Q")],
		"what to do in case of a total loss": [ytid("https://www.youtube.com/watch?v=Ynbgf5uda7Q")],
		"denied": [ytid("https://www.youtube.com/watch?v=vsdXq0WOH8M")],
		"dispute": [ytid("https://www.youtube.com/watch?v=vsdXq0WOH8M")],

		# --- Rates & discounts ---
		"rates": [ytid("https://www.youtube.com/watch?v=-QfmcoYYb5E")],
		"insurance rates": [ytid("https://www.youtube.com/watch?v=-QfmcoYYb5E")],
		"factors affecting insurance rates": [ytid("https://www.youtube.com/watch?v=-QfmcoYYb5E")],
		"driving history": [ytid("https://www.youtube.com/watch?v=e5ESP_FtOzo")],
		"impact of driving history": [ytid("https://www.youtube.com/watch?v=e5ESP_FtOzo")],
		"clean driving record": [ytid("https://www.youtube.com/watch?v=csO9yYp-vYE")],
		"maintain a clean driving record": [ytid("https://www.youtube.com/watch?v=csO9yYp-vYE")],
		"traffic violations": [ytid("https://www.youtube.com/watch?v=x-N0jCGr0Bg")],
		"impact of traffic violations": [ytid("https://www.youtube.com/watch?v=x-N0jCGr0Bg")],
		"how to lower your insurance premiums": [ytid("https://www.youtube.com/watch?v=IRi5Z7pp1K4")],
		"lower your insurance premiums": [ytid("https://www.youtube.com/watch?v=IRi5Z7pp1K4")],
		"lower premiums": [ytid("https://www.youtube.com/watch?v=IRi5Z7pp1K4")],

		# --- Driving safety & accident handling ---
		"accident": [ytid("https://www.youtube.com/watch?v=wToIYkLuwPY")],
		"car accident": [ytid("https://www.youtube.com/watch?v=wToIYkLuwPY")],
		"steps to take during a car accident": [ytid("https://www.youtube.com/watch?v=wToIYkLuwPY")],
		"safe driving": [ytid("https://www.youtube.com/watch?v=qoaF04Lsux4")],
		"do's and don'ts": [ytid("https://www.youtube.com/watch?v=qoaF04Lsux4")],
		"do's and don'ts of safe driving": [ytid("https://www.youtube.com/watch?v=qoaF04Lsux4")],
		"seasonal": [ytid("https://www.youtube.com/watch?v=46xdKVgTbJE")],
		"seasonal driving": [ytid("https://www.youtube.com/watch?v=46xdKVgTbJE")],
		"seasonal driving tips": [ytid("https://www.youtube.com/watch?v=46xdKVgTbJE")],

		# --- Study aids ---
		"terms": [ytid("https://www.youtube.com/watch?v=TVA2xaWzsSY")],
		"terms explained": [ytid("https://www.youtube.com/watch?v=TVA2xaWzsSY")],
		"common auto insurance terms": [ytid("https://www.youtube.com/watch?v=TVA2xaWzsSY")],
	}

	# Pick the *best* match. Prefer longer/more-specific keys.
	matched_ids: list[str] = []
	best_len = 0
	for k, ids in curated.items():
		key = (k or "").strip().lower()
		if not key:
			continue
		if key in t and len(key) > best_len and any(v for v in ids):
			matched_ids = ids
			best_len = len(key)

	results: list[dict[str, str]] = []
	for vid_raw in matched_ids:
		vid = ytid(vid_raw)
		if not vid:
			continue
		results.append(
			{
				"videoId": vid,
				"title": "",
				"channelTitle": "",
				"url": f"https://www.youtube.com/watch?v={vid}",
				"embedUrl": youtube_embed_for_video_id(vid),
			}
		)
	return results


def youtube_api_get_json(url: str, *, timeout_sec: float = 10.0) -> dict:
	req = urllib.request.Request(
		url,
		headers={
			"User-Agent": "Insurance-AI-Agent/1.0",
			"Accept": "application/json",
		},
	)
	with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
		data = resp.read().decode("utf-8")
		return json.loads(data)


def youtube_search_videos(*, query: str, max_results: int = 5) -> list[dict[str, str]]:
	"""Search YouTube for embeddable videos using the official Data API.

	Returns a list of dicts: {videoId, title, channelTitle, url, embedUrl}
	"""
	key = youtube_api_key()
	if not key:
		return []

	q = (query or "").strip()
	if not q:
		q = "insurance basics"

	params = {
		"part": "snippet",
		"type": "video",
		"q": q,
		"maxResults": str(max(1, min(int(max_results), 10))),
		"safeSearch": "moderate",
		"videoEmbeddable": "true",
		"videoSyndicated": "true",
		"key": key,
	}
	url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
	res = youtube_api_get_json(url)
	items = res.get("items") or []
	results: list[dict[str, str]] = []
	for it in items:
		vid = (((it or {}).get("id") or {}).get("videoId"))
		sn = (it or {}).get("snippet") or {}
		title = str(sn.get("title") or "")
		channel = str(sn.get("channelTitle") or "")
		if not vid:
			continue
		results.append(
			{
				"videoId": str(vid),
				"title": title,
				"channelTitle": channel,
				"url": f"https://www.youtube.com/watch?v={vid}",
				"embedUrl": f"https://www.youtube.com/embed/{vid}",
			}
		)
	return results


@app.post("/api/teacher/youtube")
def teacher_youtube(req: TeacherYoutubeRequest):
	"""Return a YouTube search URL (and optional embed candidates) for a module.

	We avoid scraping YouTube (TOS/rate-limit issues). Instead we provide:
	- a reliable search URL
	- an embed URL when we have a known safe match for common topics
	"""
	try:
		customer_id = int(req.customer_id)
		module_order = int(req.module_order)
		if customer_id <= 0:
			raise ValueError("customer_id must be positive")
		if module_order <= 0:
			raise ValueError("module_order must be positive")

		curriculum = insurance_mcp.get_curriculum_impl(customer_id)
		module = next((m for m in curriculum if int(m.get("order")) == module_order), None)
		if not module:
			raise HTTPException(status_code=404, detail="Module not found for this curriculum")

		module_title = str(module.get("module") or "")
		module_desc = str(module.get("description") or "")

		query = (module_title + " " + module_desc).strip()

		videos = youtube_search_videos(query=query, max_results=5)

		curated = curated_youtube_videos_for_topic(module_title) or curated_youtube_videos_for_topic(query)
		if curated:
			videos = curated + videos

		fallback_search_embed = youtube_embed_search_url(query)
		embed_candidates = [v.get("embedUrl") for v in videos if v.get("embedUrl")] or [fallback_search_embed]
		return {
			"ok": True,
			"customerId": customer_id,
			"moduleOrder": module_order,
			"moduleTitle": module_title,
			"query": query,
			"searchUrl": youtube_search_url(query),
			"embedUrl": embed_candidates[0],
			"embedCandidates": embed_candidates,
			"videos": videos,
		}
	except HTTPException:
		raise
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
