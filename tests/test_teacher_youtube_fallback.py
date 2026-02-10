import os

from fastapi.testclient import TestClient


def test_teacher_youtube_falls_back_to_embed_search_when_no_api_key(monkeypatch):
	"""Even without YOUTUBE_API_KEY, the Teacher page should get a watchable embedUrl."""
	monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

	from api_server import app
	import insurance_mcp

	customer_id = 9991
	insurance_mcp.get_customer_info_impl(
		id=customer_id,
		name="YouTube Fallback",
		age=16,
		state="CA",
		vehicleName="Honda Accord",
		coverageType="Liability",
	)
	try:
		insurance_mcp.plan_curriculum_impl(customer_id)
	except Exception:
		pass

	client = TestClient(app)
	res = client.post("/api/teacher/youtube", json={"customer_id": customer_id, "module_order": 1})
	assert res.status_code == 200
	data = res.json()
	assert data.get("ok") is True

	embed_url = data.get("embedUrl") or ""
	assert embed_url.startswith(
		("https://www.youtube.com/embed", "https://www.youtube-nocookie.com/embed")
	)

	assert (data.get("searchUrl") or "").startswith("https://www.youtube.com/")
