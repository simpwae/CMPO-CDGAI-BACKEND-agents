"""Hamza appraisal: scores reflect real contribution and therefore vary."""
from __future__ import annotations

import pytest

from app.lib.appraiser import Outcome, appraise
from app.lib.events import get_bus


@pytest.mark.asyncio
async def test_scores_vary_with_contribution():
    res = await appraise([
        Outcome(agent="shams", produced=True, chars=400, files=3),   # wrote code
        Outcome(agent="tariq", produced=True, chars=120),            # short reply
        Outcome(agent="ihsan", produced=False, errored=True),         # nothing usable
    ])
    by = {r["agent"]: r for r in res}
    # The developer who wrote files outscores the brief researcher, who outscores
    # the agent that produced nothing — i.e. scores are NOT flat.
    assert by["shams"]["score"] > by["tariq"]["score"] > by["ihsan"]["score"]
    assert by["shams"]["flag"] == "exemplary"
    assert by["ihsan"]["flag"] == "needs work"
    assert len({r["score"] for r in res}) == 3  # all different


@pytest.mark.asyncio
async def test_fallback_is_penalised():
    clean = await appraise([Outcome(agent="zain", produced=True, chars=200)])
    degraded = await appraise([Outcome(agent="zain", produced=True, chars=200, fallback=True)])
    assert degraded[0]["score"] < clean[0]["score"]


@pytest.mark.asyncio
async def test_backcompat_success_flag_still_works():
    res = await appraise([Outcome(agent="momin", success=False)])
    assert res[0]["score"] <= 30  # errored => low


@pytest.mark.asyncio
async def test_appraise_emits_events_and_reports_to_maryam():
    bus = get_bus()
    q = bus.subscribe()
    await appraise([Outcome(agent="tariq", produced=True, chars=100)])
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    types = [e.type for e in events]
    assert "appraisal" in types
    assert any(
        e.type == "a2a.message" and e.payload.get("from") == "hamza"
        and e.payload.get("to") == "maryam"
        for e in events
    )
