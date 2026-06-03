"""Google Gemini provider — the fallback path when Claude fails."""
from __future__ import annotations

from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None

    def _ensure_client(self):
        if not self._api_key:
            raise ProviderError("gemini", "GEMINI_API_KEY is not configured")
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:  # pragma: no cover
                raise ProviderError("gemini", f"google-genai SDK missing: {e}") from e
            self._client = genai.Client(api_key=self._api_key)
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

        sys_parts = [m.content for m in messages if m.role == "system"]
        if system:
            sys_parts.insert(0, system)

        # Gemini's contents expect role "user"/"model"; map assistant -> model.
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            contents.append(
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
            )

        from google.genai import types as gtypes

        config = gtypes.GenerateContentConfig(
            system_instruction="\n\n".join(sys_parts) or None,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            # SDK call is sync; run it off the event loop.
            import anyio

            resp = await anyio.to_thread.run_sync(
                lambda: client.models.generate_content(
                    model=model, contents=contents, config=config
                )
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderError("gemini", f"{type(e).__name__}: {e}") from e

        text = getattr(resp, "text", "") or ""
        usage = {}
        if getattr(resp, "usage_metadata", None):
            um = resp.usage_metadata
            usage = {
                "input_tokens": getattr(um, "prompt_token_count", None),
                "output_tokens": getattr(um, "candidates_token_count", None),
            }
        return LLMResult(
            text=text,
            provider="gemini",
            model=model,
            usage=usage,
            raw=resp,
        )
