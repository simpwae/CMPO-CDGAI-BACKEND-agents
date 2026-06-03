"""A2A in-process orchestration: dispatch -> agent runs -> task completes + events."""
from __future__ import annotations

import pytest

import app.lib.llm.router as router_mod
from app.lib.a2a.orchestrator import Orchestrator
from app.lib.events import get_bus
from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.router import ModelRouter
from app.lib.llm.types import LLMResult


class StubProvider(LLMProvider):
    name = "claude"

    async def generate(self, model, messages, **kwargs) -> LLMResult:
        return LLMResult(text="proposal: build X", provider="claude", model=model)


@pytest.fixture(autouse=True)
def stub_router():
    # Force every agent's reasoning through a deterministic stub.
    router_mod._router = ModelRouter(anthropic=StubProvider(), gemini=StubProvider())
    yield
    router_mod._router = None


@pytest.mark.asyncio
async def test_dispatch_completes_task():
    orch = Orchestrator()
    task = await orch.dispatch(skill="research", input="research idea X", assignee="tariq")
    assert task.state == "completed"
    assert task.result["provider"] == "claude"
    assert task.assignee == "tariq"
    assert any(m.sender == "tariq" for m in task.messages)


@pytest.mark.asyncio
async def test_dispatch_publishes_a2a_events():
    bus = get_bus()
    q = bus.subscribe()
    orch = Orchestrator()
    await orch.dispatch(skill="research", input="idea", assignee="tariq")

    seen_types = []
    while not q.empty():
        seen_types.append(q.get_nowait().type)
    assert "a2a.message" in seen_types
    assert "agent.status" in seen_types


@pytest.mark.asyncio
async def test_discover_lists_all_peers_no_banned():
    orch = Orchestrator()
    ids = {c["id"] for c in orch.discover()}
    assert "maryam" in ids and "ihsan" in ids
    assert "naseer" not in ids and "sohaib" not in ids


@pytest.mark.asyncio
async def test_unknown_assignee_fails_gracefully():
    orch = Orchestrator()
    task = await orch.dispatch(skill="x", input="y", assignee="ghost")
    assert task.state == "failed"
    assert "no A2A server" in task.result["error"]
