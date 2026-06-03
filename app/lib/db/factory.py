"""Repository factory: use Mongo when reachable, else fall back to memory.

This lets the app run locally without Atlas while using real persistence in
deployment. The chosen backend is reported on /api/health.
"""
from __future__ import annotations

from app.config import get_settings
from app.lib.db.base import Repository
from app.lib.db.memory import MemoryRepository

_repo: Repository | None = None


async def get_repo() -> Repository:
    global _repo
    if _repo is not None:
        return _repo

    s = get_settings()
    # Treat the default local URI as "no Atlas configured" unless a real one is set.
    if s.mongodb_uri and s.mongodb_uri != "mongodb://localhost:27017":
        try:
            from app.lib.db.mongo import MongoRepository

            repo: Repository = MongoRepository(s.mongodb_uri, s.mongodb_db)
            if await repo.ping():
                _repo = repo
                return _repo
        except Exception:
            pass  # fall through to memory

    _repo = MemoryRepository()
    return _repo


def reset_repo() -> None:
    """For tests."""
    global _repo
    _repo = None
