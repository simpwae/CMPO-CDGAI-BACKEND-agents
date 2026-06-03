"""Process-wide async event bus.

One bus carries everything the dashboard cares about: A2A messages, MCP tool
calls, model-router provider choices, agent status changes, and AG-UI
human-in-the-loop approval events. The AG-UI SSE endpoint (M7) subscribes to
this bus and streams events to the operator browser.

Events are also persisted by subscribers (M6) — the bus itself is fire-and-forget.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# Monotonic counter avoids Date.now()/uuid and keeps ordering deterministic.
_seq = 0


def _next_seq() -> int:
    global _seq
    _seq += 1
    return _seq


@dataclass
class Event:
    type: str                       # e.g. "a2a.message", "mcp.tool_call", "approval.request"
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = field(default_factory=_next_seq)

    def to_dict(self) -> dict:
        return {"seq": self.seq, "type": self.type, **self.payload}


class EventBus:
    def __init__(self, history: int = 200):
        self._subscribers: set[asyncio.Queue] = set()
        self._history: deque[Event] = deque(maxlen=history)

    async def publish(self, type: str, payload: dict | None = None) -> Event:
        event = Event(type=type, payload=payload or {})
        self._history.append(event)
        for q in list(self._subscribers):
            # Non-blocking: a slow consumer never stalls the publisher.
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        # Replay recent history so a freshly-connected dashboard isn't empty.
        for event in self._history:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                break
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def recent(self, limit: int = 50) -> list[dict]:
        return [e.to_dict() for e in list(self._history)[-limit:]]


_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
