"""A2A HTTP surface: AgentCard discovery + task dispatch."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.lib.a2a.orchestrator import get_orchestrator
from app.lib.agents.cards import ROSTER

router = APIRouter(prefix="/a2a", tags=["a2a"])


@router.get("/agents")
async def discover() -> dict:
    return {"agents": get_orchestrator().discover()}


@router.get("/{agent_id}/.well-known/agent-card.json")
async def agent_card(agent_id: str) -> dict:
    card = ROSTER.get(agent_id.lower())
    if card is None:
        raise HTTPException(404, f"unknown agent '{agent_id}'")
    return card.to_dict()


class DispatchBody(BaseModel):
    skill: str
    input: str
    assignee: str
    requester: str = "maryam"
    context: str | None = None


@router.post("/dispatch")
async def dispatch(body: DispatchBody) -> dict:
    if body.assignee.lower() not in ROSTER:
        raise HTTPException(404, f"unknown assignee '{body.assignee}'")
    task = await get_orchestrator().dispatch(
        skill=body.skill,
        input=body.input,
        assignee=body.assignee,
        requester=body.requester,
        context=body.context,
    )
    return task.to_dict()
