"""Flow trigger endpoints. Flows run in the background and surface via AG-UI SSE."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.lib.flows import FLOWS, start_flow

router = APIRouter(prefix="/api/flows", tags=["flows"])


@router.get("")
async def list_flows() -> dict:
    return {"flows": list(FLOWS.keys())}


@router.post("/{name}")
async def run_flow(name: str) -> dict:
    try:
        start_flow(name)
    except KeyError:
        raise HTTPException(404, f"unknown flow '{name}'")
    return {"started": name}
