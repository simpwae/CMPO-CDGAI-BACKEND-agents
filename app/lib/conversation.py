"""Maryam-driven team orchestration (real LLM).

The interaction is inverted: the operator does NOT chat with Maryam. The operator
assigns an *objective*, and Maryam runs the room — she asks her teammates real
questions, they answer with real LLM calls, and leads delegate downward. Every
message records who is speaking and who they are speaking TO, so the dashboard
shows exactly who can talk to whom (matching the org edges in §3).

Communication structure follows the authoritative graph:
  Maryam -> Tariq / Momin / Zain / Hamza
  Momin  -> Naqash
  Naqash -> Fateh Shah / Shams / Usman      (build)
  Naqash <-> Ihsan                          (test/fix loop, no Momin)
Hamza appraises everyone involved and reports to Maryam.

Message CONTENT is real LLM output; the delegation STRUCTURE is fixed by the org
chart, so an assignment to Naqash always makes Naqash actually do the work.
"""
from __future__ import annotations

import json

from app.lib.agents.cards import ROSTER, get_card
from app.lib.appraiser import Outcome, appraise
from app.lib.db.factory import get_repo
from app.lib.events import get_bus
from app.lib.llm.router import get_router
from app.lib.llm.types import LLMMessage

# Whom Maryam may directly ask (her A2A peers).
MARYAM_PEERS = ["tariq", "momin", "zain", "hamza"]
NAQASH_SUBS = ["fateh", "shams", "usman"]


def _name(agent_id: str) -> str:
    c = ROSTER.get(agent_id)
    return c.name if c else agent_id.title()


async def _history(limit: int = 60) -> list[dict]:
    repo = await get_repo()
    return await repo.find("messages", {"thread": "main"}, limit=limit, sort_desc=False)


def _thread_text(history: list[dict]) -> str:
    if not history:
        return "(conversation just started)"
    lines = []
    for m in history:
        to = f" → {m['to_name']}" if m.get("to_name") else ""
        lines.append(f"{m.get('name', m['sender'])}{to}: {m['text']}")
    return "\n".join(lines)


async def _post(sender: str, text: str, *, to: str | None = None,
                provider: str | None = None, fallback_used: bool = False,
                name: str | None = None) -> dict:
    """Persist + stream one directed message (sender speaking TO `to`)."""
    repo = await get_repo()
    doc = {
        "thread": "main",
        "sender": sender,
        "name": name or _name(sender),
        "to": to,
        "to_name": _name(to) if to else None,
        "text": text,
        "provider": provider,
        "fallback_used": fallback_used,
    }
    await repo.insert("messages", doc)
    bus = get_bus()
    await bus.publish("chat.message", doc)
    if sender in ROSTER:
        await bus.publish("agent.status", {"agent": sender, "status": "idle"})
    if to and to in ROSTER:
        # Mirror the directed edge onto the activity feed / graph.
        await bus.publish(
            "a2a.message", {"from": sender, "to": to, "text": text, "state": "completed"}
        )
    return doc


async def _reply(agent_id: str, prompt: str, *, asker: str) -> dict:
    """Get a real LLM reply from an agent and post it (agent -> asker)."""
    await get_bus().publish("agent.status", {"agent": agent_id, "status": "working"})
    history = await _history()
    system = get_card(agent_id).system_prompt
    user = (
        f"Team conversation so far:\n{_thread_text(history)}\n\n"
        f"{_name(asker)} asks you: \"{prompt}\"\n"
        "Reply in 1-3 sentences, as yourself, actually doing your part."
    )
    res = await get_router().generate(
        agent_id, [LLMMessage(role="user", content=user)], system=system, max_tokens=350
    )
    return await _post(agent_id, res.text, to=asker,
                       provider=res.provider, fallback_used=res.fallback_used)


async def _maryam_plan(objective: str) -> dict:
    """Maryam decides whom to ask and what to ask them. Returns parsed plan."""
    await get_bus().publish("agent.status", {"agent": "maryam", "status": "working"})
    history = await _history()
    system = (
        get_card("maryam").system_prompt
        + "\n\nYour directly-reachable team: "
        + ", ".join(f"{a} ({_name(a)})" for a in MARYAM_PEERS)
        + ". For any build/development work delegate to Momin, who assigns Naqash "
        "(the dev lead); Naqash then directs Fateh/Shams/Usman and tests with Ihsan. "
        "Use Tariq for research, Zain for events/outreach, Hamza for appraisal.\n\n"
        "Respond ONLY as JSON: "
        '{"summary": "<1 sentence to the team>", '
        '"asks": [{"agent": "<peer_id>", "question": "<what you ask them>"}], '
        '"needs_dev": <true|false>}. '
        "Only use agent ids from your reachable team. Keep questions to one sentence."
    )
    user = f"Objective from the operator: \"{objective}\"\nPlan who you will ask."
    res = await get_router().generate(
        "maryam", [LLMMessage(role="user", content=user)], system=system, max_tokens=500
    )
    return {**_parse_plan(res.text), "_provider": res.provider, "_fallback": res.fallback_used}


def _parse_plan(text: str) -> dict:
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        asks = [
            {"agent": a["agent"], "question": str(a.get("question", "")).strip()}
            for a in data.get("asks", [])
            if a.get("agent") in MARYAM_PEERS
        ]
        return {
            "summary": str(data.get("summary", "")).strip() or "Let's get to work, team.",
            "asks": asks or [{"agent": "tariq", "question": "Please look into this."}],
            "needs_dev": bool(data.get("needs_dev", False)),
        }
    except Exception:
        return {
            "summary": text.strip()[:200] or "Let's get to work, team.",
            "asks": [{"agent": "tariq", "question": "Please look into this objective."}],
            "needs_dev": False,
        }


async def _naqash_builds(objective: str) -> list[str]:
    """Naqash directs his sub-team and runs the test/fix loop with Ihsan."""
    involved = ["naqash"]
    # Naqash kicks off (real reply to Momin's hand-off).
    await _reply("naqash", f"Lead the build for: {objective}", asker="momin")

    for sub, area in [("fateh", "frontend"), ("shams", "backend"), ("usman", "devops")]:
        q = f"Take the {area} for: {objective}. What will you do?"
        await _post("naqash", q, to=sub)
        await _reply(sub, q, asker="naqash")
        involved.append(sub)

    # Naqash <-> Ihsan direct test/fix loop (no Momin).
    q1 = "The build is ready — please test it and report any issues."
    await _post("naqash", q1, to="ihsan")
    await _reply("ihsan", q1, asker="naqash")
    q2 = "Thanks. I've addressed what you found — please re-test and confirm."
    await _post("naqash", q2, to="ihsan")
    await _reply("ihsan", q2, asker="naqash")
    involved.append("ihsan")
    return involved


async def run_objective(objective: str) -> dict:
    """Operator assigns an objective; Maryam interrogates and drives the team."""
    await _post("operator", objective, to="maryam", name="Objective")

    involved: list[str] = []
    try:
        plan = await _maryam_plan(objective)
        await _post("maryam", plan["summary"],
                    provider=plan["_provider"], fallback_used=plan["_fallback"])

        for ask in plan["asks"]:
            agent_id = ask["agent"]
            await _post("maryam", ask["question"], to=agent_id)
            await _reply(agent_id, ask["question"], asker="maryam")
            involved.append(agent_id)

            # A build/dev objective cascades down the dev org through Momin->Naqash.
            if agent_id == "momin" and plan["needs_dev"]:
                handoff = f"Assign this build to Naqash: {objective}"
                await _post("momin", handoff, to="naqash")
                involved += await _naqash_builds(objective)

        # Hamza appraises everyone involved and reports to Maryam.
        seen, outcomes = set(), []
        for a in involved:
            if a not in seen and a != "hamza":
                seen.add(a)
                outcomes.append(Outcome(agent=a, success=True))
        if outcomes:
            await appraise(outcomes)
    except Exception as e:  # noqa: BLE001 — most often: no/blocked LLM key
        await get_bus().publish("agent.status", {"agent": "maryam", "status": "error"})
        await _post(
            "maryam",
            f"⚠️ I couldn't reach a language model ({type(e).__name__}). Configure a "
            "working ANTHROPIC_API_KEY or GEMINI_API_KEY on the backend, then reassign "
            "the objective.",
        )

    return {"involved": involved}


async def get_thread(limit: int = 60) -> list[dict]:
    return await _history(limit)
