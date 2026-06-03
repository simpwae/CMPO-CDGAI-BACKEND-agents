"""Chat/objective surface.

The operator assigns an objective; Maryam then drives the team conversation.
The operator is NOT a chat participant — Maryam asks the questions.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.lib.conversation import get_thread, run_objective

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ObjectiveBody(BaseModel):
    text: str          # the objective to hand to Maryam
    sender: str = "operator"


@router.get("")
async def thread(limit: int = 60) -> dict:
    return {"messages": await get_thread(limit)}


@router.post("")
async def assign_objective(body: ObjectiveBody) -> dict:
    # Maryam orchestrates in the background; the team conversation streams via SSE.
    asyncio.create_task(run_objective(body.text))
    return {"accepted": True}
