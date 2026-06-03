"""Chat surface. The human IS Maryam (the primary user): she gives orders and
tags a teammate with @name. The tagged teammate's branch then cascades."""
from __future__ import annotations

import asyncio

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
    # Cascade runs in the background; the team conversation streams via SSE.
    asyncio.create_task(run_order(body.text, body.to))
    return {"accepted": True}
