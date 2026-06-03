"""Groq provider (OpenAI-compatible, fast free inference — Llama/Qwen/GPT-OSS).

NOTE: Groq (gsk_ keys, api.groq.com) is distinct from xAI's Grok (xai- keys).
Thin httpx call against the OpenAI-compatible Chat Completions endpoint.
"""
from __future__ import annotations

import asyncio

import httpx

from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError

BASE_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    name = "groq"

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
            raise ProviderError("groq", "GROQ_API_KEY is not configured")

        payload_msgs = []
        if system:
            payload_msgs.append({"role": "system", "content": system})
        for m in messages:
            role = m.role if m.role in ("system", "user", "assistant") else "user"
            payload_msgs.append({"role": role, "content": m.content})

        body = {
            "model": model,
            "messages": payload_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = None
                # Free-tier bursts hit 429; back off briefly and retry (bounded so
                # we stay within serverless time limits).
                for attempt in range(3):
                    resp = await client.post(BASE_URL, headers=headers, json=body)
                    if resp.status_code != 429:
                        break
                    if attempt == 2:
                        break
                    ra = resp.headers.get("retry-after")
                    try:
                        wait = float(ra) if ra else 1.0 + attempt
                    except ValueError:
                        wait = 1.0 + attempt
                    await asyncio.sleep(min(wait, 2.5))
            if resp.status_code != 200:
                raise ProviderError("groq", f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderError("groq", f"{type(e).__name__}: {e}") from e

        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage", {}) or {}
        return LLMResult(
            text=text,
            provider="groq",
            model=model,
            usage={
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            },
            raw=data,
        )
