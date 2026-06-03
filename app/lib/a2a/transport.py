"""Transport abstraction so A2A can move cross-host later without touching agents.

The MVP uses InProcessTransport (direct in-memory dispatch). A future
HttpJsonRpcTransport can implement the same interface to call remote AgentCards
over JSON-RPC/REST.
"""
from __future__ import annotations

from typing import Protocol

from app.lib.a2a.messages import Task


class A2AHandler(Protocol):
    async def handle(self, task: Task) -> Task: ...


class Transport(Protocol):
    async def send(self, agent_id: str, task: Task) -> Task: ...


class InProcessTransport:
    """Routes tasks directly to in-process A2A servers keyed by agent id."""

    def __init__(self):
        self._handlers: dict[str, A2AHandler] = {}

    def register(self, agent_id: str, handler: A2AHandler) -> None:
        self._handlers[agent_id] = handler

    async def send(self, agent_id: str, task: Task) -> Task:
        handler = self._handlers.get(agent_id)
        if handler is None:
            task.state = "failed"
            task.result = {"error": f"no A2A server registered for '{agent_id}'"}
            return task
        return await handler.handle(task)
