"""In-memory repository — used for local dev without Atlas and for tests.

Does NOT survive process restarts; the Mongo repository is the persistent one.
"""
from __future__ import annotations

from app.lib.db.base import COLLECTIONS


class MemoryRepository:
    backend = "memory"

    def __init__(self):
        self._data: dict[str, list[dict]] = {c: [] for c in COLLECTIONS}
        self._seq = 0

    def _store(self, collection: str) -> list[dict]:
        return self._data.setdefault(collection, [])

    def _matches(self, doc: dict, query: dict) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    async def insert(self, collection: str, doc: dict) -> dict:
        self._seq += 1
        doc = {"_id": f"mem-{self._seq:06d}", "_seq": self._seq, **doc}
        self._store(collection).append(doc)
        return doc

    async def find(self, collection, query=None, *, limit=100, sort_desc=True) -> list[dict]:
        query = query or {}
        rows = [d for d in self._store(collection) if self._matches(d, query)]
        rows.sort(key=lambda d: d.get("_seq", 0), reverse=sort_desc)
        return rows[:limit]

    async def update_one(self, collection, query, patch, *, upsert=False) -> None:
        for d in self._store(collection):
            if self._matches(d, query):
                d.update(patch)
                return
        if upsert:
            await self.insert(collection, {**query, **patch})

    async def count(self, collection, query=None) -> int:
        query = query or {}
        return sum(1 for d in self._store(collection) if self._matches(d, query))

    async def ping(self) -> bool:
        return True
