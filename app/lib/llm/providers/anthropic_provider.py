"""Anthropic (Claude) provider — the primary path for every agent."""
from __future__ import annotations

from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError


class AnthropicProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None  # lazily created so missing SDK/key fails cleanly

    def _ensure_client(self):
        if not self._api_key:
            raise ProviderError("claude", "ANTHROPIC_API_KEY is not configured")
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as e:  # pragma: no cover
                raise ProviderError("claude", f"anthropic SDK missing: {e}") from e
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        model: str,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResult:
        client = self._ensure_client()

        # Anthropic keeps the system prompt out of the messages array.
        sys_parts = [m.content for m in messages if m.role == "system"]
        if system:
            sys_parts.insert(0, system)
        convo = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        try:
            resp = await client.messages.create(
                model=model,
                system="\n\n".join(sys_parts) or None,
                messages=convo,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:  # noqa: BLE001 — any failure becomes a fallback trigger
            raise ProviderError("claude", f"{type(e).__name__}: {e}") from e

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        usage = {}
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
        return LLMResult(
            text=text,
            provider="claude",
            model=model,
            usage=usage,
            raw=resp,
        )
