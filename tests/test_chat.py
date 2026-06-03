"""Hierarchical cascading delegation: Maryam -> Momin -> Naqash -> Shams."""
from __future__ import annotations

import json

import pytest

import app.lib.db.factory as db_factory
import app.lib.llm.router as router_mod
from app.lib.conversation import get_thread, parse_mention, run_order
from app.lib.db.memory import MemoryRepository
from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.router import ModelRouter
from app.lib.llm.types import LLMResult


class Hierarchical(LLMProvider):
    """Each manager delegates down its own branch; leaves do the work."""

    name = "claude"

    async def generate(self, model, messages, *, system=None, **kwargs) -> LLMResult:
        s = system or ""
        if "ONLY as JSON" in s:
            # Branch on which manager is planning (their persona is in the system).
            if s.startswith("You are Momin"):
                asks = [{"agent": "naqash", "question": "Assign this build."}]
            else:  # Naqash
                asks = [{"agent": "shams", "question": "Build the backend."}]
            return LLMResult(
                text=json.dumps({"summary": "On it.", "asks": asks}),
                provider="claude", model=model,
            )
        return LLMResult(text="Done, backend implemented.", provider="claude", model=model)


@pytest.fixture(autouse=True)
def _env():
    db_factory._repo = MemoryRepository()
    router_mod._router = ModelRouter(anthropic=Hierarchical(), gemini=Hierarchical())
    yield
    db_factory._repo = None
    router_mod._router = None


@pytest.mark.asyncio
async def test_maryam_tags_momin_and_it_cascades():
    # The human IS Maryam: she tags Momin, and it cascades autonomously.
    await run_order("@momin Build a publishing toolkit backend")
    thread = await get_thread()
    edges = {(m["sender"], m["to"]) for m in thread if m.get("to")}
    assert ("maryam", "momin") in edges      # Maryam's order
    assert ("momin", "naqash") in edges       # Momin decides -> Naqash
    assert ("naqash", "shams") in edges       # Naqash assigns -> Shams
    assert ("shams", "naqash") in edges       # Shams does the work


@pytest.mark.asyncio
async def test_mention_parsing_resolves_ids_and_names():
    assert parse_mention("@momin build it")[0] == "momin"
    assert parse_mention("@Naqash ship it")[0] == "naqash"
    assert parse_mention("@Fateh do frontend")[0] == "fateh"   # first-name match
    assert parse_mention("no mention here")[0] is None


@pytest.mark.asyncio
async def test_shams_reply_carries_provider_badge():
    await run_order("@momin Build the backend")
    thread = await get_thread()
    shams = [m for m in thread if m["sender"] == "shams"]
    assert shams and shams[-1]["provider"] == "claude"


class CodingProvider(LLMProvider):
    """A developer that emits a real fenced code block."""

    name = "claude"

    async def generate(self, model, messages, *, system=None, **kwargs) -> LLMResult:
        text = (
            "Implemented the books endpoint.\n"
            "```python app/books.py\n"
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            "@router.get('/books')\n"
            "def list_books():\n"
            "    return []\n"
            "```"
        )
        return LLMResult(text=text, provider="claude", model=model)


@pytest.mark.asyncio
async def test_developer_emits_visible_code_artifact():
    import app.lib.db.factory as dbf
    import app.lib.llm.router as rm
    from app.lib.events import get_bus

    dbf._repo = MemoryRepository()
    rm._router = ModelRouter(anthropic=CodingProvider(), gemini=CodingProvider())
    bus = get_bus()
    q = bus.subscribe()
    try:
        await run_order("@shams Build the books backend API")
        artifacts = []
        while not q.empty():
            ev = q.get_nowait()
            if ev.type == "artifact":
                artifacts.append(ev.payload)
        assert artifacts, "developer should emit a code artifact"
        art = artifacts[0]
        assert art["agent"] == "shams"
        assert art["filename"] == "app/books.py"
        assert art["language"] == "python"
        assert "APIRouter" in art["code"]
    finally:
        dbf._repo = None
        rm._router = None
