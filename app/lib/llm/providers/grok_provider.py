"""xAI Grok provider (OpenAI-compatible Chat Completions API).

Added as an extra fallback in the router chain. Grok's endpoint mirrors the
OpenAI schema, so this is a thin httpx call. Activates as soon as the xAI team
backing the key has credits/licenses.
"""
from __future__ import annotations

import httpx

from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError

BASE_URL = "https://api.x.ai/v1/chat/completions"


class GrokProvider(LLMProvider):
    name = "grok"

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
            raise ProviderError("grok", "GROK_API_KEY is not configured")

        payload_msgs = []
        if system:
            payload_msgs.append({"role": "system", "content": system})
        for m in messages:
            role = m.role if m.role in ("system", "user", "assistant") else "user"
            payload_msgs.append({"role": role, "content": m.content})

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    BASE_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": model,
                        "messages": payload_msgs,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
            if resp.status_code != 200:
                raise ProviderError("grok", f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderError("grok", f"{type(e).__name__}: {e}") from e

        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage", {}) or {}
        return LLMResult(
            text=text,
            provider="grok",
            model=model,
            usage={
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            },
            raw=data,
        )
