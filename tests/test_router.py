"""Unit tests for the model router's Claude->Gemini fallback behavior."""
from __future__ import annotations

import pytest

from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.router import ModelRouter
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError


class FakeClaude(LLMProvider):
    name = "claude"

    def __init__(self, fail: bool):
        self.fail = fail
        self.calls = 0

    async def generate(self, model, messages, **kwargs) -> LLMResult:
        self.calls += 1
        if self.fail:
            raise ProviderError("claude", "forced failure")
        return LLMResult(text="from-claude", provider="claude", model=model)


class FakeGemini(LLMProvider):
    name = "gemini"

    def __init__(self):
        self.calls = 0

    async def generate(self, model, messages, **kwargs) -> LLMResult:
        self.calls += 1
        return LLMResult(text="from-gemini", provider="gemini", model=model)


MSGS = [LLMMessage(role="user", content="hi")]


@pytest.mark.asyncio
async def test_claude_primary_succeeds():
    claude, gemini = FakeClaude(fail=False), FakeGemini()
    router = ModelRouter(anthropic=claude, gemini=gemini)
    res = await router.generate("tariq", MSGS)
    assert res.provider == "claude"
    assert res.fallback_used is False
    assert gemini.calls == 0


@pytest.mark.asyncio
async def test_falls_back_to_gemini_when_claude_fails():
    claude, gemini = FakeClaude(fail=True), FakeGemini()
    router = ModelRouter(anthropic=claude, gemini=gemini)
    res = await router.generate("maryam", MSGS)
    assert res.provider == "gemini"
    assert res.fallback_used is True
    assert claude.calls == 2  # primary + one retry before fallback
    assert gemini.calls == 1
    assert any("forced failure" in e for e in res.error_chain)


class FakeGrok(LLMProvider):
    name = "grok"

    def __init__(self):
        self.calls = 0

    async def generate(self, model, messages, **kwargs) -> LLMResult:
        self.calls += 1
        return LLMResult(text="from-grok", provider="grok", model=model)


@pytest.mark.asyncio
async def test_falls_through_to_grok_when_claude_and_gemini_fail():
    claude = FakeClaude(fail=True)

    class DeadGemini(LLMProvider):
        name = "gemini"

        async def generate(self, model, messages, **kwargs):
            raise ProviderError("gemini", "down")

    grok = FakeGrok()
    router = ModelRouter(anthropic=claude, gemini=DeadGemini(), grok=grok)
    res = await router.generate("tariq", MSGS)
    assert res.provider == "grok"
    assert res.fallback_used is True
    assert grok.calls == 1
    assert any("forced failure" in e for e in res.error_chain)


@pytest.mark.asyncio
async def test_lead_agent_uses_lead_model():
    claude, gemini = FakeClaude(fail=False), FakeGemini()
    router = ModelRouter(anthropic=claude, gemini=gemini)
    res = await router.generate("maryam", MSGS)
    assert res.model == router._s.claude_model_lead


@pytest.mark.asyncio
async def test_observer_receives_provider():
    seen = {}

    async def obs(payload):
        seen.update(payload)

    router = ModelRouter(anthropic=FakeClaude(False), gemini=FakeGemini(), observer=obs)
    await router.generate("zain", MSGS)
    assert seen["provider"] == "claude"
    assert seen["agent"] == "zain"
