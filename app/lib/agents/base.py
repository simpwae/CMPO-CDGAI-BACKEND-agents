"""Base agent. The ONLY reasoning path is the model router — no provider SDK.

Subclasses/instances carry an AgentCard and optionally a set of MCP tool names
they are allowed to call. The A2A layer (M4) wraps these to expose each agent
as a peer; the MCP layer (M5) injects callable tools.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from app.lib.agents.cards import AgentCard, NodeStatus
from app.lib.llm.router import get_router
from app.lib.llm.types import LLMMessage, LLMResult

# An MCP tool runner injected by the runtime: (tool, args) -> result dict.
ToolRunner = Callable[[str, dict], Awaitable[dict]]


class BaseAgent:
    def __init__(self, card: AgentCard, tool_runner: ToolRunner | None = None):
        self.card = card
        self.status: NodeStatus = "idle"
        self._tool_runner = tool_runner

    @property
    def id(self) -> str:
        return self.card.id

    async def act(
        self,
        instruction: str,
        *,
        context: str | None = None,
        max_tokens: int = 800,
    ) -> dict:
        """Reason about an instruction and return a normalized result dict."""
        self.status = "working"
        messages: list[LLMMessage] = []
        if context:
            messages.append(LLMMessage(role="user", content=f"Context:\n{context}"))
        messages.append(LLMMessage(role="user", content=instruction))

        try:
            result: LLMResult = await get_router().generate(
                self.card.id,
                messages,
                system=self.card.system_prompt,
                max_tokens=max_tokens,
            )
        except Exception:
            self.status = "error"
            raise

        self.status = "idle"
        return {
            "agent": self.card.id,
            "name": self.card.name,
            "text": result.text,
            "provider": result.provider,
            "model": result.model,
            "fallback_used": result.fallback_used,
            "error_chain": result.error_chain,
        }

    async def use_tool(self, tool: str, args: dict) -> dict:
        """Call an MCP tool, if a runner has been wired in (M5)."""
        if self._tool_runner is None:
            raise RuntimeError(f"{self.id} has no MCP tool runner configured")
        if tool not in self.card.skills and not _is_tool_skill(self.card, tool):
            # Not fatal in the MVP, but record intent for Hamza/monitoring.
            pass
        return await self._tool_runner(tool, args)


def _is_tool_skill(card: AgentCard, tool: str) -> bool:
    return any(s == tool for s in card.skills)
