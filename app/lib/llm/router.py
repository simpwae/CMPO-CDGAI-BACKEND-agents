"""Model router — the single choke point for ALL agent reasoning.

For every call the router walks an ordered provider chain (configurable via
`LLM_ORDER`). The first provider gets a retry; the rest get one attempt each.
A provider whose key is unset raises immediately and is skipped. The first
success returns a normalized LLMResult carrying `provider` + `fallback_used`
so the dashboard shows which model served each step.

Default order puts the working free Groq tier first; set `LLM_ORDER` to
"claude,gemini,grok,groq" once an Anthropic key is available. No agent code may
import a provider SDK directly — everything goes through `generate(...)`.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from app.config import get_settings
from app.lib.llm.providers.anthropic_provider import AnthropicProvider
from app.lib.llm.providers.base import LLMProvider
from app.lib.llm.providers.gemini_provider import GeminiProvider
from app.lib.llm.providers.grok_provider import GrokProvider
from app.lib.llm.providers.groq_provider import GroqProvider
from app.lib.llm.types import LLMMessage, LLMResult, ProviderError

# Agents that reason on the stronger ("lead") model tier.
LEAD_AGENTS = {"maryam", "naqash"}

DEFAULT_ORDER = ["claude", "gemini", "grok", "groq"]

# Optional observer invoked after every call so the AG-UI activity feed can
# surface which provider served each step.
CallObserver = Callable[[dict], Awaitable[None] | None]


class ModelRouter:
    def __init__(
        self,
        anthropic: LLMProvider | None = None,
        gemini: LLMProvider | None = None,
        grok: LLMProvider | None = None,
        groq: LLMProvider | None = None,
        observer: CallObserver | None = None,
        order: list[str] | None = None,
    ):
        s = get_settings()
        self._providers: dict[str, LLMProvider] = {
            "claude": anthropic or AnthropicProvider(s.anthropic_api_key),
            "gemini": gemini or GeminiProvider(s.gemini_api_key),
            "grok": grok or GrokProvider(s.grok_api_key),
            "groq": groq or GroqProvider(s.groq_api_key),
        }
        self._order = order or DEFAULT_ORDER
        self._observer = observer
        self._s = s

    def set_observer(self, observer: CallObserver) -> None:
        self._observer = observer

    def _model_for(self, provider: str, agent: str) -> str:
        lead = agent.lower() in LEAD_AGENTS
        models = {
            "claude": (self._s.claude_model_lead, self._s.claude_model_default),
            "gemini": (self._s.gemini_model_lead, self._s.gemini_model_default),
            "grok": (self._s.grok_model_lead, self._s.grok_model_default),
            "groq": (self._s.groq_model_lead, self._s.groq_model_default),
        }[provider]
        return models[0] if lead else models[1]

    async def generate(
        self,
        agent: str,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResult:
        errors: list[str] = []

        for idx, name in enumerate(self._order):
            provider = self._providers.get(name)
            if provider is None:
                continue
            # The primary provider gets one retry; fallbacks get a single shot.
            attempts = 2 if idx == 0 else 1
            for attempt in range(attempts):
                try:
                    result = await provider.generate(
                        self._model_for(name, agent),
                        messages,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    result.fallback_used = idx > 0
                    result.error_chain = errors
                    await self._emit(agent, result)
                    return result
                except Exception as e:  # noqa: BLE001
                    label = name if attempts == 1 else f"{name} attempt {attempt + 1}"
                    errors.append(f"{label}: {e}")

        raise ProviderError("router", " | ".join(errors) or "no providers configured")

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
        _router = ModelRouter(order=get_settings().llm_order.split(","))
    return _router


async def generate(agent: str, messages: list[LLMMessage], **kwargs) -> LLMResult:
    """Module-level convenience matching the spec's `generate({agent, messages})`."""
    return await get_router().generate(agent, messages, **kwargs)
