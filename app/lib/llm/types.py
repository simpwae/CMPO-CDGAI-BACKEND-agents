"""Normalized types shared across LLM providers and the router."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]
Provider = Literal["claude", "gemini"]


@dataclass
class LLMMessage:
    role: Role
    content: str


@dataclass
class LLMResult:
    """One normalized shape regardless of which provider served the call."""

    text: str
    provider: Provider
    model: str
    fallback_used: bool = False
    # When Claude failed before Gemini answered, the failure reason is kept here
    # so the dashboard activity feed can explain why the fallback fired.
    error_chain: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "fallback_used": self.fallback_used,
            "error_chain": self.error_chain,
            "usage": self.usage,
        }


class ProviderError(Exception):
    """Raised by a provider when it cannot serve a request.

    The router treats any ProviderError (and any other exception) from the
    primary provider as a trigger to fall back.
    """

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")
