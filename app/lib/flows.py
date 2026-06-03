"""The four core flows (spec §6), wired through the real protocol layers.

Each flow drives genuine A2A dispatches, MCP tool calls, AG-UI approvals, and
Hamza appraisals. Agent free-text reasoning is best-effort: if no LLM key is
configured the model router fails gracefully and the flow still progresses
(MCP tools, approvals, appraisals all work without an LLM), so the dashboard is
fully demoable out of the box and richer once keys are set.

Flows run as background tasks because, in assist mode, approval steps block
until the operator responds in the browser.
"""
from __future__ import annotations

import asyncio

from app.lib.a2a.orchestrator import get_orchestrator
from app.lib.agui.approvals import get_approvals
from app.lib.appraiser import Outcome, appraise
from app.lib.events import get_bus
from app.lib.mcp.client import get_mcp_client


async def _say(frm: str, to: str, text: str, **extra) -> None:
    """Emit a narrative A2A message so the feed shows every coordination step."""
    await get_bus().publish(
        "a2a.message", {"from": frm, "to": to, "text": text, "state": "completed", **extra}
    )


async def _reason(agent: str, instruction: str, *, requester: str) -> dict:
    """Best-effort agent reasoning via A2A dispatch; never raises to the flow."""
    try:
        task = await get_orchestrator().dispatch(
            skill="act", input=instruction, assignee=agent, requester=requester
        )
        return task.result or {}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# ---------------------------------------------------------------- idea flow
async def idea_flow() -> None:
    """Tariq -> Maryam approval -> Momin -> Naqash (+subs) -> Ihsan loop -> Hamza."""
    await _reason("tariq", "Research a promising new product idea and propose it.",
                  requester="maryam")
    await _say("tariq", "maryam", "Proposal: an AI-assisted publishing toolkit.")

    decision = await get_approvals().request(
        title="Tariq proposes: AI-assisted publishing toolkit",
        detail="Approve this research idea for development?",
        requester="tariq",
        kind="idea",
    )
    if not decision["approved"]:
        await _say("maryam", "tariq", "Idea rejected. Hold for now.")
        await appraise([Outcome(agent="tariq", success=True, note="proposal reviewed")])
        return

    await _say("maryam", "momin", "Approved. Please assign this build to Naqash.")
    await _reason("momin", "Assign the approved toolkit build to Naqash.",
                  requester="maryam")
    await _say("momin", "naqash", "Build the AI-assisted publishing toolkit.")

    # Naqash directs the three sub-agents.
    for sub, what in [("fateh", "frontend"), ("shams", "backend"), ("usman", "devops")]:
        await _say("naqash", sub, f"Take the {what} for the toolkit.")
        await _reason(sub, f"Implement the {what} for the toolkit.", requester="naqash")

    # Naqash <-> Ihsan direct test/fix loop (no Momin).
    await _say("naqash", "ihsan", "Build ready — please test.")
    await _reason("ihsan", "Test the toolkit build and report issues.", requester="naqash")
    await _say("ihsan", "naqash", "Found 1 issue in export. Please fix.", state="working")
    await _say("naqash", "ihsan", "Fixed export. Re-test please.")
    await _say("ihsan", "naqash", "All tests pass. ✅")

    # Hamza appraises everyone involved.
    await appraise([
        Outcome(agent="tariq", success=True, note="idea approved & built"),
        Outcome(agent="momin", success=True),
        Outcome(agent="naqash", success=True),
        Outcome(agent="fateh", success=True),
        Outcome(agent="shams", success=True),
        Outcome(agent="usman", success=True),
        Outcome(agent="ihsan", success=True, note="caught and verified a fix"),
    ])


# --------------------------------------------------------------- event flow
async def event_flow() -> None:
    """Zain searches events (MCP) -> Maryam approval -> Momin if dev component."""
    found = await get_mcp_client().call_tool("events.search", {"kind": "hackathon"},
                                             caller="zain")
    event = found["events"][0]
    await _say("zain", "maryam", f"Found event: {event['name']} ({event['date']}).")

    decision = await get_approvals().request(
        title=f"Zain found: {event['name']}",
        detail=f"Approve participation? Dev component: {event['has_dev_component']}.",
        requester="zain",
        kind="event",
        context={"event": event},
    )
    if not decision["approved"]:
        await _say("maryam", "zain", "Event participation rejected.")
        await appraise([Outcome(agent="zain", success=True, note="event reviewed")])
        return

    outcomes = [Outcome(agent="zain", success=True, note="sourced approved event")]
    if event["has_dev_component"]:
        await _say("maryam", "momin", f"{event['name']} has a dev component — looping you in.")
        await _reason("momin", f"Coordinate dev participation for {event['name']}.",
                      requester="maryam")
        outcomes.append(Outcome(agent="momin", success=True, note="joined for dev component"))
    else:
        await _say("zain", "maryam", "No dev component — I'll proceed solo.")

    await appraise(outcomes)


# --------------------------------------------------------------- comms flow
async def comms_flow() -> None:
    """Zain handles LinkedIn/email via MCP, then posts a daily report to Maryam."""
    await get_mcp_client().call_tool(
        "linkedin.post", {"text": "CDG AI shipping multi-agent ops! 🚀"}, caller="zain"
    )
    await get_mcp_client().call_tool(
        "email.reply", {"to": "partner@example.com", "subject": "Re: collab", "body": "Thanks!"},
        caller="zain",
    )
    await _say("zain", "maryam", "Daily report: 1 LinkedIn post, 1 email reply handled.")
    await appraise([Outcome(agent="zain", success=True, note="daily comms + report")])


FLOWS = {
    "idea": idea_flow,
    "event": event_flow,
    "comms": comms_flow,
}


def start_flow(name: str) -> asyncio.Task:
    if name not in FLOWS:
        raise KeyError(name)
    return asyncio.create_task(FLOWS[name]())
