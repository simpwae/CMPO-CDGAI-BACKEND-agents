"""OpenRouter provider (OpenAI-compatible aggregator; free models available).

Acts as a second working fallback so deep cascades survive Groq rate-limits.
Free models are themselves rate-limited upstream, so we retry on 429.
"""
from __future__ import annotations

import asyncio

import httpx

from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def generate(
        self,
        model: str,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResult:
        if not self._api_key:
            raise ProviderError("openrouter", "OPENROUTER_API_KEY is not configured")

        payload_msgs = []
        if system:
            payload_msgs.append({"role": "system", "content": system})
        for m in messages:
            role = m.role if m.role in ("system", "user", "assistant") else "user"
            payload_msgs.append({"role": role, "content": m.content})

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://cmpo-cdgai-hackaton.vercel.app",
            "X-Title": "CDGAI",
        }
        body = {
            "model": model,
            "messages": payload_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = None
                for attempt in range(3):
                    resp = await client.post(BASE_URL, headers=headers, json=body)
                    if resp.status_code != 429:
                        break
                    if attempt == 2:
                        break
                    await asyncio.sleep(1.0 + attempt)
            if resp.status_code != 200:
                raise ProviderError("openrouter", f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderError("openrouter", f"{type(e).__name__}: {e}") from e

        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage", {}) or {}
        return LLMResult(
            text=text,
            provider="openrouter",
            model=model,
            usage={
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            },
            raw=data,
        )
