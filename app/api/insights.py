"""Appraisals + learning-log read endpoints for the dashboard panels."""
from __future__ import annotations

from fastapi import APIRouter

from app.lib.db.factory import get_repo

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/appraisals")
async def appraisals(limit: int = 20) -> dict:
    repo = await get_repo()
    rows = await repo.find("appraisals", limit=limit)
    # Latest appraisal per agent, in score order.
    latest: dict[str, dict] = {}
    for r in rows:  # rows are newest-first; keep first seen per agent
        latest.setdefault(r["agent"], r)
    out = sorted(latest.values(), key=lambda a: a["score"], reverse=True)
    return {"appraisals": out}


@router.get("/learning/count")
async def learning_count() -> dict:
    repo = await get_repo()
    return {"count": await repo.count("learning_log")}


@router.get("/learning")
async def learning(limit: int = 50) -> dict:
    repo = await get_repo()
    return {"entries": await repo.find("learning_log", limit=limit)}
