"""Hamza — the performance appraiser.

Hamza monitors agent outcomes (read-only) and produces per-agent appraisals:
a 0-100 score, an optional flag, and a short note. Scores are derived
deterministically from observed outcomes so the panel is meaningful even when
no LLM key is configured; an optional model-written note can be layered on top.
Every appraisal is published to the bus (persisted to the appraisals collection)
and summarized back to Maryam.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.lib.events import get_bus


@dataclass
class Outcome:
    agent: str
    success: bool
    fallback_used: bool = False
    note: str = ""


def _score(o: Outcome) -> tuple[int, str]:
    score = 70
    if o.success:
        score += 20
    else:
        score -= 40
    if o.fallback_used:
        score -= 10  # degraded path (Claude fell back to Gemini)
    score = max(0, min(100, score))

    if score >= 85:
        flag = "exemplary"
    elif score < 50:
        flag = "underperforming"
    else:
        flag = "ok"
    return score, flag


async def appraise(outcomes: list[Outcome]) -> list[dict]:
    """Appraise each agent involved in a flow; report to Maryam."""
    bus = get_bus()
    appraisals: list[dict] = []
    for o in outcomes:
        score, flag = _score(o)
        note = o.note or (
            "completed assigned work"
            if o.success
            else "failed to complete assigned work"
        )
        if o.fallback_used:
            note += " (served via Gemini fallback)"
        record = {
            "agent": o.agent,
            "score": score,
            "flag": flag,
            "note": note,
            "by": "hamza",
        }
        appraisals.append(record)
        await bus.publish("appraisal", record)

    # Report summary up to Maryam.
    avg = round(sum(a["score"] for a in appraisals) / len(appraisals)) if appraisals else 0
    await bus.publish(
        "a2a.message",
        {
            "from": "hamza",
            "to": "maryam",
            "text": f"Appraised {len(appraisals)} agents, avg score {avg}.",
            "state": "completed",
        },
    )
    return appraisals
