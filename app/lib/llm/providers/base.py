"""Provider interface. Each provider turns normalized input into an LLMResult."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.lib.llm.types import LLMMessage, LLMResult


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResult:
        """Produce a normalized result or raise ProviderError on any failure."""
        ...
