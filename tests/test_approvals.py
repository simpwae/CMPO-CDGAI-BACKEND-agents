"""AG-UI human-in-the-loop approvals: assist waits for operator, auto self-resolves."""
from __future__ import annotations

import asyncio

import pytest

import app.lib.runtime as runtime
from app.lib.agui.approvals import ApprovalRegistry
from app.lib.events import get_bus


@pytest.fixture(autouse=True)
def _assist_mode():
    runtime.set_mode("assist")
    yield
    runtime._mode = None


@pytest.mark.asyncio
async def test_assist_mode_waits_for_operator():
    reg = ApprovalRegistry()
    task = asyncio.create_task(
        reg.request(title="Idea X", detail="...", requester="tariq", kind="idea")
    )
    await asyncio.sleep(0.01)
    assert len(reg.pending()) == 1  # blocked, awaiting operator

    pid = reg.pending()[0]["id"]
    await reg.resolve(pid, approved=True)
    decision = await task
    assert decision["approved"] is True
    assert decision["by"] == "operator"
    assert reg.pending() == []


@pytest.mark.asyncio
async def test_auto_mode_self_resolves():
    runtime.set_mode("auto")
    reg = ApprovalRegistry()
    decision = await reg.request(
        title="Event Y", detail="...", requester="zain", kind="event"
    )
    assert decision["approved"] is True
    assert decision["auto"] is True
    assert decision["by"] == "agent-maryam"


@pytest.mark.asyncio
async def test_assist_decision_emits_learning_event():
    bus = get_bus()
    q = bus.subscribe()
    reg = ApprovalRegistry()
    task = asyncio.create_task(
        reg.request(title="Idea", detail="d", requester="tariq", kind="idea")
    )
    await asyncio.sleep(0.01)
    await reg.resolve(reg.pending()[0]["id"], approved=False)
    await task

    types = []
    while not q.empty():
        types.append(q.get_nowait().type)
    assert "approval.request" in types
    assert "decision" in types
    assert "learning" in types  # human decisions become training data
