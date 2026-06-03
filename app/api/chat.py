"""Chat surface. The human IS Maryam (the primary user): she gives orders and
tags a teammate with @name. The tagged teammate's branch then cascades.

The cascade runs synchronously within the request so it works on serverless
hosts (where fire-and-forget background tasks are killed when the function
returns). Every message is persisted as it is produced, so clients that poll
GET /api/chat see progress even if a long cascade is cut short by a timeout.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.lib.conversation import get_thread, run_order

router = APIRouter(prefix="/api/chat", tags=["chat"])


class OrderBody(BaseModel):
    text: str               # Maryam's order, may contain an @mention
    to: str | None = None   # optional explicit recipient (overrides @mention)


@router.get("")
async def thread(limit: int = 60) -> dict:
    return {"messages": await get_thread(limit)}


@router.post("")
async def give_order(body: OrderBody) -> dict:
    result = await run_order(body.text, body.to)
    return {"accepted": True, "involved": result.get("involved", []),
            "messages": await get_thread(60)}
