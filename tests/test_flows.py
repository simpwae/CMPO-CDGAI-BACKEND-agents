"""End-to-end flow QA (spec §6): idea, event, comms — run in auto mode."""
from __future__ import annotations

import pytest

import app.lib.llm.router as router_mod
import app.lib.runtime as runtime
from app.lib.flows import comms_flow, event_flow, idea_flow
from app.lib.events import get_bus
from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.router import ModelRouter
from app.lib.llm.types import LLMResult


class Stub(LLMProvider):
    name = "claude"

    async def generate(self, model, messages, **kwargs) -> LLMResult:
        return LLMResult(text="ok", provider="claude", model=model)


@pytest.fixture(autouse=True)
def _env():
    runtime.set_mode("auto")  # approvals self-resolve, no operator needed
    router_mod._router = ModelRouter(anthropic=Stub(), gemini=Stub())
    yield
    runtime._mode = None
    router_mod._router = None


def _collect(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


@pytest.mark.asyncio
async def test_idea_flow_runs_end_to_end():
    bus = get_bus()
    q = bus.subscribe()
    await idea_flow()
    events = _collect(q)
    types = [e.type for e in events]
    assert "approval.request" in types
    assert "decision" in types
    assert "appraisal" in types

    msgs = [e.payload for e in events if e.type == "a2a.message"]
    pairs = {(m.get("from"), m.get("to")) for m in msgs}
    # Naqash <-> Ihsan direct loop both directions...
    assert ("naqash", "ihsan") in pairs
    assert ("ihsan", "naqash") in pairs
    # ...and Momin never sits in the test/fix loop.
    assert ("momin", "ihsan") not in pairs
    assert ("ihsan", "momin") not in pairs


@pytest.mark.asyncio
async def test_event_flow_loops_in_momin_for_dev_component():
    bus = get_bus()
    q = bus.subscribe()
    await event_flow()
    events = _collect(q)
    # events.search ran via MCP
    assert any(e.type == "mcp.tool_call" and e.payload.get("tool") == "events.search"
               for e in events)
    msgs = [e.payload for e in events if e.type == "a2a.message"]
    # First mock event has a dev component -> Maryam loops in Momin.
    assert any(m.get("from") == "maryam" and m.get("to") == "momin" for m in msgs)


@pytest.mark.asyncio
async def test_comms_flow_posts_and_reports():
    bus = get_bus()
    q = bus.subscribe()
    await comms_flow()
    events = _collect(q)
    tools = {e.payload.get("tool") for e in events if e.type == "mcp.tool_call"}
    assert "linkedin.post" in tools
    assert "email.reply" in tools
    assert any(
        e.type == "a2a.message" and e.payload.get("from") == "zain"
        and e.payload.get("to") == "maryam"
        for e in events
    )
