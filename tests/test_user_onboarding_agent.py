import sys
import types

import pytest

from langchain import user_onboarding_agent as uoa


class _FakeAgent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def astream(self, payload):
        for c in self._chunks:
            yield c


@pytest.mark.asyncio
async def test_run_agent_prints_last_assistant_message(capsys):
    agent = _FakeAgent(
        chunks=[
            {"messages": [{"role": "assistant", "content": "First"}]},
            {"messages": [{"role": "assistant", "content": "Second"}]},
        ]
    )

    await uoa.run_agent(agent, "hi")

    out = capsys.readouterr().out
    assert out.strip() == "Second"


@pytest.mark.asyncio
async def test_run_agent_handles_message_object_shape(capsys):

    class _Msg:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    agent = _FakeAgent(
        chunks=[
            {"messages": [_Msg("assistant", "Hello")]}  
        ]
    )

    await uoa.run_agent(agent, "hi")

    out = capsys.readouterr().out
    assert out.strip() == "Hello"


@pytest.mark.asyncio
async def test_onboard_calls_run_agent_twice_and_plans_curriculum(monkeypatch):
    calls = []

    async def fake_run_agent(agent, query):
        calls.append((agent, query))

    monkeypatch.setattr(uoa, "run_agent", fake_run_agent)

    fake_curr = types.SimpleNamespace()

    async def fake_init_curriculum_agent():
        return "CURR_AGENT"

    fake_curr.initialize_agent = fake_init_curriculum_agent
    sys.modules["langchain.curriculum_planner_agent"] = fake_curr

    await uoa.onboard("ONBOARD_AGENT", "Hey. My id is 2, my name is Sam")

    assert calls[0] == ("ONBOARD_AGENT", "Hey. My id is 2, my name is Sam")
    assert calls[1] == ("CURR_AGENT", "Plan a curriculum for customer id 2")


@pytest.mark.asyncio
async def test_onboard_no_id_only_runs_onboarding(monkeypatch):
    calls = []

    async def fake_run_agent(agent, query):
        calls.append((agent, query))

    monkeypatch.setattr(uoa, "run_agent", fake_run_agent)

    await uoa.onboard("ONBOARD_AGENT", "Hello there")

    assert calls == [("ONBOARD_AGENT", "Hello there")]
