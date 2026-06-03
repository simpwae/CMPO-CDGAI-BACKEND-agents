"""Hamza appraisal scoring + event emission."""
from __future__ import annotations

import pytest

from app.lib.appraiser import Outcome, appraise
from app.lib.events import get_bus


@pytest.mark.asyncio
async def test_success_scores_high_failure_low():
    res = await appraise(
        [
            Outcome(agent="naqash", success=True),
            Outcome(agent="ihsan", success=False),
        ]
    )
    by_agent = {r["agent"]: r for r in res}
    assert by_agent["naqash"]["score"] == 90
    assert by_agent["naqash"]["flag"] == "exemplary"
    assert by_agent["ihsan"]["score"] == 30
    assert by_agent["ihsan"]["flag"] == "underperforming"


@pytest.mark.asyncio
async def test_fallback_penalised():
    res = await appraise([Outcome(agent="zain", success=True, fallback_used=True)])
    assert res[0]["score"] == 80
    assert "fallback" in res[0]["note"]


@pytest.mark.asyncio
async def test_appraise_emits_events_and_reports_to_maryam():
    bus = get_bus()
    q = bus.subscribe()
    await appraise([Outcome(agent="tariq", success=True)])
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    types = [e.type for e in events]
    assert "appraisal" in types
    # Hamza reports a summary to Maryam.
    assert any(
        e.type == "a2a.message" and e.payload.get("from") == "hamza"
        and e.payload.get("to") == "maryam"
        for e in events
    )
