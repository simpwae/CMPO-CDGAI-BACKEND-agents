"""AG-UI surface: a single SSE event stream to the operator browser plus the
human-in-the-loop control endpoints (approve/reject, pending list, mode toggle).

The stream carries every bus event in an AG-UI-style envelope so the dashboard
renders messages, MCP tool calls, agent status, approvals, and decisions live.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.lib.agui.approvals import get_approvals
from app.lib.events import get_bus
from app.lib.runtime import get_mode, set_mode

router = APIRouter(prefix="/api/agui", tags=["agui"])


@router.get("/stream")
async def stream():
    bus = get_bus()

    async def gen():
        q = bus.subscribe()
        try:
            # Greet so the client knows the stream is live.
            yield {"event": "message", "data": json.dumps({"type": "agui.connected"})}
            while True:
                event = await q.get()
                yield {"event": "message", "data": json.dumps(event.to_dict())}
        except asyncio.CancelledError:
            raise
        finally:
            bus.unsubscribe(q)

    return EventSourceResponse(gen())


@router.get("/recent")
async def recent(limit: int = 50) -> dict:
    return {"events": get_bus().recent(limit)}


@router.get("/pending")
async def pending() -> dict:
    return {"pending": get_approvals().pending(), "mode": get_mode()}


class ApproveBody(BaseModel):
    approval_id: str
    approved: bool
    by: str = "operator"


@router.post("/approve")
async def approve(body: ApproveBody) -> dict:
    try:
        decision = await get_approvals().resolve(
            body.approval_id, approved=body.approved, by=body.by
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"decision": decision}


class ModeBody(BaseModel):
    mode: str  # "assist" | "auto"


@router.get("/mode")
async def read_mode() -> dict:
    return {"mode": get_mode()}


@router.post("/mode")
async def update_mode(body: ModeBody) -> dict:
    try:
        mode = set_mode(body.mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    from app.lib.runtime import persist_mode

    await persist_mode()
    await get_bus().publish("mode.changed", {"mode": mode})
    return {"mode": mode}
