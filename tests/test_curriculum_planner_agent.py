import pytest

from langchain.curriculum_planner_agent import handle_query as handle_query
import langchain.curriculum_planner_agent as cpa


class _FakeTool:
    def __init__(self, name, ret=None, exc=None):
        self.name = name
        self._ret = ret
        self._exc = exc
        self.calls = []

    async def ainvoke(self, payload):
        self.calls.append(payload)
        if self._exc is not None:
            raise self._exc
        return self._ret


@pytest.mark.asyncio
async def test_handle_query_show_calls_get_curriculum(monkeypatch, capsys):
    get_tool = _FakeTool(
        "get_curriculum",
        ret=[{"module": "M1"}, {"module": "M2"}],
    )
    plan_tool = _FakeTool("plan_curriculum", ret=[{"module": "NEW"}])

    async def fake_setup_mcp_client():
        return [plan_tool, get_tool]

    monkeypatch.setattr(cpa, "setup_mcp_client", fake_setup_mcp_client)

    await cpa.handle_query("Show the curriculum for customer id 2")

    assert get_tool.calls == [{"customer_id": 2}]
    assert plan_tool.calls == []

    out = capsys.readouterr().out
    assert "1. M1" in out
    assert "2. M2" in out


@pytest.mark.asyncio
async def test_handle_query_plan_skips_if_curriculum_exists(monkeypatch, capsys):
    existing = [{"module": "Already there"}]

    get_tool = _FakeTool("get_curriculum", ret=existing)
    plan_tool = _FakeTool("plan_curriculum", ret=[{"module": "NEW"}])

    async def fake_setup_mcp_client():
        return [plan_tool, get_tool]

    monkeypatch.setattr(cpa, "setup_mcp_client", fake_setup_mcp_client)

    await cpa.handle_query("Plan a curriculum for customer id 5")

    assert get_tool.calls == [{"customer_id": 5}]
    assert plan_tool.calls == []

    out = capsys.readouterr().out.strip().lower()
    assert out.endswith("it already exists in the database")


@pytest.mark.asyncio
async def test_handle_query_plan_creates_when_missing(monkeypatch, capsys):
    get_tool = _FakeTool("get_curriculum", exc=ValueError("No curriculum found for customer 7"))
    plan_tool = _FakeTool("plan_curriculum", ret=[{"module": "Intro"}, {"module": "Deductibles"}])

    async def fake_setup_mcp_client():
        return [plan_tool, get_tool]

    monkeypatch.setattr(cpa, "setup_mcp_client", fake_setup_mcp_client)

    await cpa.handle_query("Please create a curriculum for customer 7")

    assert get_tool.calls == [{"customer_id": 7}]
    assert plan_tool.calls == [{"customer_id": 7}]

    out = capsys.readouterr().out.strip().lower()
    assert out.endswith("done")


def test_extract_customer_id():
    assert cpa.extract_customer_id("customer id 12") == 12
    assert cpa.extract_customer_id("12") == 12
    assert cpa.extract_customer_id("id: abc") is None


def test_has_curriculum_and_unwrap_payload_variants():
    assert cpa.has_curriculum([{"module": "X"}]) is True
    assert cpa.has_curriculum([]) is False
    assert cpa.has_curriculum({"curriculum": [{"module": "X"}]}) is True
    assert cpa.has_curriculum("No curriculum found") is False
    assert cpa.unwrap_payload([{"text": "{\"curriculum\": [{\"module\": \"X\"}]}"}]) == [{"module": "X"}]
