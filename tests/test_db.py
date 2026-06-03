"""DB layer: memory repository CRUD + factory falls back to memory locally."""
from __future__ import annotations

import pytest

from app.lib.db.factory import get_repo, reset_repo
from app.lib.db.memory import MemoryRepository


@pytest.fixture(autouse=True)
def _reset():
    reset_repo()
    yield
    reset_repo()


@pytest.mark.asyncio
async def test_insert_and_find():
    repo = MemoryRepository()
    await repo.insert("decisions", {"kind": "approve", "agent": "tariq"})
    await repo.insert("decisions", {"kind": "reject", "agent": "zain"})
    rows = await repo.find("decisions")
    assert len(rows) == 2
    assert rows[0]["kind"] == "reject"  # newest first


@pytest.mark.asyncio
async def test_count_with_query():
    repo = MemoryRepository()
    await repo.insert("learning_log", {"mode": "assist"})
    await repo.insert("learning_log", {"mode": "assist"})
    await repo.insert("learning_log", {"mode": "auto"})
    assert await repo.count("learning_log", {"mode": "assist"}) == 2


@pytest.mark.asyncio
async def test_update_one_upsert():
    repo = MemoryRepository()
    await repo.update_one("agents", {"id": "maryam"}, {"status": "working"}, upsert=True)
    rows = await repo.find("agents", {"id": "maryam"})
    assert rows[0]["status"] == "working"


@pytest.mark.asyncio
async def test_factory_falls_back_to_memory_without_atlas(monkeypatch):
    # With only the default local URI configured, the factory uses memory.
    import app.lib.db.factory as factory

    class FakeSettings:
        mongodb_uri = "mongodb://localhost:27017"
        mongodb_db = "cdgai"

    monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
    factory.reset_repo()
    repo = await get_repo()
    assert repo.backend == "memory"
