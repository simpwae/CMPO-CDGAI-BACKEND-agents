"""Roster + graph API consumed by the dashboard's network view."""
from __future__ import annotations

from fastapi import APIRouter

from app.lib.agents.cards import EDGES, list_cards
from app.lib.agents.roster import all_agents

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def get_roster() -> dict:
    agents = all_agents()
    return {
        "agents": [
            {**card.to_dict(), "status": agents[card.id].status}
            for card in list_cards()
        ],
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "label": e.label,
                "kind": e.kind,
                "bidirectional": e.bidirectional,
            }
            for e in EDGES
        ],
    }
