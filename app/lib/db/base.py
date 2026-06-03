"""Repository interface. All persistence goes through this — never touch a
driver directly from agent/flow code."""
from __future__ import annotations

from typing import Any, Protocol

# The six collections the system persists (spec §2).
COLLECTIONS = (
    "agents",        # agent identity + last known status
    "decisions",     # Maryam approve/reject decisions
    "messages",      # A2A messages
    "tool_calls",    # MCP tool-call logs
    "appraisals",    # Hamza's per-agent appraisals
    "learning_log",  # human-Maryam decisions recorded for learning
    "config",        # persisted runtime config (e.g. Maryam mode)
    "artifacts",     # code files produced by the developer agents
)


class Repository(Protocol):
    backend: str  # "mongo" | "memory"

    async def insert(self, collection: str, doc: dict) -> dict: ...

    async def find(
        self, collection: str, query: dict | None = None, *, limit: int = 100, sort_desc: bool = True
    ) -> list[dict]: ...

    async def update_one(
        self, collection: str, query: dict, patch: dict, *, upsert: bool = False
    ) -> None: ...

    async def count(self, collection: str, query: dict | None = None) -> int: ...

    async def ping(self) -> bool: ...
