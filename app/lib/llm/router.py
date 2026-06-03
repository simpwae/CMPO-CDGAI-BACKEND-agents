"""Model router — the single choke point for ALL agent reasoning.

Order of operations for every call:
  1. Resolve the agent's tier (lead agents get the stronger model).
  2. Call Anthropic (Claude). On any failure, retry once.
  3. If Claude still fails, transparently fall back to Gemini.
  4. Return a normalized LLMResult carrying `provider` + `fallback_used`
     so the dashboard can show which model served each step.

No agent code may import a provider SDK directly — everything goes through
`generate(...)`.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from app.config import get_settings
from app.lib.llm.providers.anthropic_provider import AnthropicProvider
from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.providers.gemini_provider import GeminiProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError

# Agents that reason on the stronger ("lead") model tier.
LEAD_AGENTS = {"maryam", "naqash"}

# Optional observer invoked after every call so the AG-UI activity feed can
# surface which provider served each step. Set via set_call_observer().
CallObserver = Callable[[dict], Awaitable[None] | None]


class ModelRouter:
    def __init__(
        self,
        anthropic: LLMProvider | None = None,
        gemini: LLMProvider | None = None,
        observer: CallObserver | None = None,
    ):
        s = get_settings()
        self._anthropic = anthropic or AnthropicProvider(s.anthropic_api_key)
        self._gemini = gemini or GeminiProvider(s.gemini_api_key)
        self._observer = observer
        self._s = s

    def set_observer(self, observer: CallObserver) -> None:
        self._observer = observer

    def _models_for(self, agent: str) -> tuple[str, str]:
        """Return (claude_model, gemini_model) for the agent's tier."""
        if agent.lower() in LEAD_AGENTS:
            return self._s.claude_model_lead, self._s.gemini_model_lead
        return self._s.claude_model_default, self._s.gemini_model_default

    async def generate(
        self,
        agent: str,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResult:
        claude_model, gemini_model = self._models_for(agent)
        errors: list[str] = []

        # --- Primary: Claude, with one retry ---
        for attempt in range(2):
            try:
                result = await self._anthropic.generate(
                    claude_model,
                    messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                result.error_chain = errors
                await self._emit(agent, result)
                return result
            except Exception as e:  # noqa: BLE001
                errors.append(f"claude attempt {attempt + 1}: {e}")

        # --- Fallback: Gemini ---
        try:
            result = await self._gemini.generate(
                gemini_model,
                messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            result.fallback_used = True
            result.error_chain = errors
            await self._emit(agent, result)
            return result
        except Exception as e:  # noqa: BLE001
            errors.append(f"gemini: {e}")
            raise ProviderError("router", " | ".join(errors)) from e

    async def _emit(self, agent: str, result: LLMResult) -> None:
        if not self._observer:
            return
        payload = {"agent": agent, **result.to_dict()}
        out = self._observer(payload)
        if hasattr(out, "__await__"):
            await out  # type: ignore[func-returns-value]


_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


async def generate(agent: str, messages: list[LLMMessage], **kwargs) -> LLMResult:
    """Module-level convenience matching the spec's `generate({agent, messages})`."""
    return await get_router().generate(agent, messages, **kwargs)
