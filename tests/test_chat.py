"""Maryam-driven objective orchestration: Maryam asks the team, Naqash builds."""
from __future__ import annotations

import json

import pytest

import app.lib.db.factory as db_factory
import app.lib.llm.router as router_mod
from app.lib.conversation import get_thread, run_objective
from app.lib.db.memory import MemoryRepository
from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.router import ModelRouter
from app.lib.llm.types import LLMResult


class Scripted(LLMProvider):
    """Maryam plans a dev objective via Momin; everyone else replies as themselves."""

    name = "claude"

    async def generate(self, model, messages, *, system=None, **kwargs) -> LLMResult:
        if system and "ONLY as JSON" in system:
            body = json.dumps(
                {
                    "summary": "Team, let's build this.",
                    "asks": [{"agent": "momin", "question": "Please assign this build."}],
                    "needs_dev": True,
                }
            )
            return LLMResult(text=body, provider="claude", model=model)
        return LLMResult(text="On it.", provider="claude", model=model)


@pytest.fixture(autouse=True)
def _env():
    db_factory._repo = MemoryRepository()
    router_mod._router = ModelRouter(anthropic=Scripted(), gemini=Scripted())
    yield
    db_factory._repo = None
    router_mod._router = None


@pytest.mark.asyncio
async def test_objective_cascades_through_momin_to_naqash_and_subteam():
    await run_objective("Build a publishing toolkit")
    thread = await get_thread()
    senders = [m["sender"] for m in thread]

    # Operator assigns; Maryam drives.
    assert senders[0] == "operator"
    assert "maryam" in senders and "momin" in senders
    # Dev objective reaches Naqash, who actually works with the full sub-team...
    for sub in ("naqash", "fateh", "shams", "usman", "ihsan"):
        assert sub in senders, sub


@pytest.mark.asyncio
async def test_messages_are_directed_who_talks_to_whom():
    await run_objective("Build a publishing toolkit")
    thread = await get_thread()
    edges = {(m["sender"], m["to"]) for m in thread if m.get("to")}
    # Org-chart edges show up explicitly in the log.
    assert ("operator", "maryam") in edges
    assert ("maryam", "momin") in edges
    assert ("momin", "naqash") in edges
    assert ("naqash", "fateh") in edges
    assert ("naqash", "ihsan") in edges
    # Naqash<->Ihsan loop never routes through Momin.
    assert ("momin", "ihsan") not in edges


@pytest.mark.asyncio
async def test_naqash_replies_carry_provider_badge():
    await run_objective("Build a publishing toolkit")
    thread = await get_thread()
    naqash_msgs = [m for m in thread if m["sender"] == "naqash" and m.get("provider")]
    assert naqash_msgs and naqash_msgs[0]["provider"] == "claude"
