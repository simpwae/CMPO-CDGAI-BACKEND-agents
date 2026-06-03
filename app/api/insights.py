"""Appraisals + learning-log read endpoints for the dashboard panels."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.lib.db.factory import get_repo

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/llm/status")
async def llm_status() -> dict:
    """Safe diagnostic: which provider keys are present (booleans only) + a live
    test call. Use this to verify env vars on a deployed host."""
    s = get_settings()
    keys = {
        "groq": bool(s.groq_api_key),
        "claude": bool(s.anthropic_api_key),
        "gemini": bool(s.gemini_api_key),
        "grok": bool(s.grok_api_key),
    }
    from app.lib.llm.router import get_router
    from app.lib.llm.types import LLMMessage

    try:
        r = await get_router().generate(
            "tariq", [LLMMessage(role="user", content="reply with: ok")], max_tokens=5
        )
        live = {"ok": True, "provider": r.provider, "model": r.model}
    except Exception as e:  # noqa: BLE001
        live = {"ok": False, "error": str(e)[:400]}
    return {"keys_configured": keys, "llm_order": s.llm_order, "live_test": live}


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


@router.get("/artifacts")
async def artifacts(limit: int = 60) -> dict:
    repo = await get_repo()
    return {"artifacts": await repo.find("artifacts", limit=limit)}


@router.get("/workspace")
async def workspace(project: str) -> dict:
    from app.lib.workspace import list_tree

    return {"project": project, "files": list_tree(project)}
