"""Hamza — the performance appraiser.

Hamza monitors what each agent ACTUALLY did during a run and scores them on it,
so appraisals vary and mean something:
  - did they produce real output (not empty / not errored)?
  - how substantive was their contribution (reply length)?
  - for developers: how many files did they actually write?
  - for managers: did they delegate?
  - was the call served on a degraded fallback provider?

Every appraisal is published to the bus (persisted to the appraisals collection)
and summarized back to Maryam.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.lib.events import get_bus


@dataclass
class Outcome:
    agent: str
    produced: bool = True   # contributed non-empty output
    chars: int = 0          # length of their contribution
    files: int = 0          # files written (developers)
    delegated: int = 0      # sub-tasks delegated (managers)
    fallback: bool = False  # served on a fallback provider
    errored: bool = False
    note: str = ""

    # Back-compat: older callers passed success=/fallback_used=.
    def __init__(self, agent, success=None, fallback_used=None, produced=True,
                 chars=0, files=0, delegated=0, fallback=False, errored=False, note=""):
        self.agent = agent
        self.produced = produced if success is None else bool(success)
        self.errored = errored if success is None else (not success)
        self.fallback = fallback or bool(fallback_used)
        self.chars = chars
        self.files = files
        self.delegated = delegated
        self.note = note


def _score(o: Outcome) -> tuple[int, str]:
    if o.errored or not o.produced:
        score = 28
    else:
        score = 55
        score += min(20, o.chars // 12)     # substantive replies earn up to +20
        score += min(22, o.files * 7)       # developers: +7 per file, up to +22
        score += min(8, o.delegated * 4)    # managers: credit for delegating
        if o.fallback:
            score -= 7                       # degraded path
    score = max(0, min(100, score))

    if score >= 82:
        flag = "exemplary"
    elif score >= 65:
        flag = "solid"
    elif score >= 45:
        flag = "mixed"
    else:
        flag = "needs work"
    return score, flag


def _auto_note(o: Outcome) -> str:
    if o.errored or not o.produced:
        return "did not produce usable output"
    bits = []
    if o.files:
        bits.append(f"wrote {o.files} file{'s' if o.files != 1 else ''}")
    if o.delegated:
        bits.append(f"delegated {o.delegated} task{'s' if o.delegated != 1 else ''}")
    if not bits:
        bits.append("contributed to the task")
    note = ", ".join(bits)
    if o.fallback:
        note += " (fallback provider)"
    return note


async def appraise(outcomes: list[Outcome]) -> list[dict]:
    """Appraise each agent involved in a run; report to Maryam."""
    bus = get_bus()
    appraisals: list[dict] = []
    for o in outcomes:
        score, flag = _score(o)
        record = {
            "agent": o.agent,
            "score": score,
            "flag": flag,
            "note": o.note or _auto_note(o),
            "by": "hamza",
        }
        appraisals.append(record)
        await bus.publish("appraisal", record)

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
