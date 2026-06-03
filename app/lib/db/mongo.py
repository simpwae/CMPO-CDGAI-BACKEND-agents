"""MongoDB repository using motor, with a cached/global client.

Vercel-style serverless reuses connections across warm invocations, so the
client is created once at module scope and reused — never per request.
"""
from __future__ import annotations

from typing import Any

_client: Any = None  # motor.AsyncIOMotorClient — cached across warm invocations


def _get_client(uri: str):
    global _client
    if _client is None:
        from motor.motor_asyncio import AsyncIOMotorClient

        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    return _client


class MongoRepository:
    backend = "mongo"

    def __init__(self, uri: str, db_name: str):
        self._db = _get_client(uri)[db_name]

    async def insert(self, collection: str, doc: dict) -> dict:
        doc = dict(doc)
        res = await self._db[collection].insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return doc

    async def find(self, collection, query=None, *, limit=100, sort_desc=True) -> list[dict]:
        cursor = (
            self._db[collection]
            .find(query or {})
            .sort("_id", -1 if sort_desc else 1)
            .limit(limit)
        )
        rows = await cursor.to_list(length=limit)
        for r in rows:
            r["_id"] = str(r["_id"])
        return rows

    async def update_one(self, collection, query, patch, *, upsert=False) -> None:
        await self._db[collection].update_one(query, {"$set": patch}, upsert=upsert)

    async def count(self, collection, query=None) -> int:
        return await self._db[collection].count_documents(query or {})

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False
