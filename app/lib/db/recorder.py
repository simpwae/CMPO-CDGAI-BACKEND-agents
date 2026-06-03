"""Bridge: subscribe to the event bus and persist relevant events to Mongo.

Runs as a single background task for the app's lifetime. Maps event types to
collections so the activity feed, tool-call log, decisions, appraisals, and
learning log all survive restarts.
"""
from __future__ import annotations

import asyncio

from app.lib.db.factory import get_repo
from app.lib.events import get_bus

# event type -> collection
_ROUTING = {
    "a2a.message": "messages",
    "decision": "decisions",
    "appraisal": "appraisals",
    "learning": "learning_log",
}


async def _run() -> None:
    bus = get_bus()
    repo = await get_repo()
    q = bus.subscribe()
    while True:
        event = await q.get()
        try:
            if event.type == "mcp.tool_call" and event.payload.get("phase") == "result":
                await repo.insert("tool_calls", event.to_dict())
            elif event.type in _ROUTING:
                await repo.insert(_ROUTING[event.type], event.to_dict())
        except Exception:
            # Persistence must never crash the event stream.
            pass


def start_recorder() -> asyncio.Task:
    return asyncio.create_task(_run())
