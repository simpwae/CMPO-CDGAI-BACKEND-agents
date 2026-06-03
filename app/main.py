"""CDGAI multi-agent operations system — FastAPI entrypoint.

Backend holds the agent runtime, the model router, the A2A orchestration layer,
the MCP client (tools), and the AG-UI SSE stream that talks to the operator
browser. Agent logic lives under app/lib so it can later be lifted to a
dedicated runtime without touching the API surface.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import a2a as a2a_api
from app.api import agents as agents_api
from app.api import agui as agui_api
from app.api import chat as chat_api
from app.api import flows as flows_api
from app.api import insights as insights_api
from app.api import mcp as mcp_api
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.lib.db.recorder import start_recorder
    from app.lib.runtime import load_mode_from_db

    await load_mode_from_db()
    recorder = start_recorder()
    app.state.recorder = recorder
    try:
        yield
    finally:
        recorder.cancel()


app = FastAPI(
    title="CDGAI — Multi-Agent Operations",
    version="0.1.0",
    description="MCP + A2A + AG-UI multi-agent system. Main Agent: Maryam.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(agents_api.router)
app.include_router(a2a_api.router)
app.include_router(mcp_api.router)
app.include_router(agui_api.router)
app.include_router(insights_api.router)
app.include_router(flows_api.router)
app.include_router(chat_api.router)


@app.get("/api/health")
async def health() -> dict:
    from app.lib.db.factory import get_repo

    repo = await get_repo()
    return {
        "status": "ok",
        "service": "cdgai-backend",
        "maryam_mode": settings.maryam_mode,
        "db_backend": repo.backend,
    }
