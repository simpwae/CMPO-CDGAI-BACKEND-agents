"""A2A message/task model (aligned with A2A spec v0.3 shapes, trimmed for MVP)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TaskState = Literal[
    "submitted", "working", "input-required", "completed", "failed", "canceled"
]


def _id(prefix: str, n: int) -> str:
    return f"{prefix}-{n:06d}"


_counter = 0


def _next() -> int:
    global _counter
    _counter += 1
    return _counter


@dataclass
class Message:
    role: Literal["user", "agent"]
    text: str
    sender: str          # agent id (or "operator")
    recipient: str       # agent id
    id: str = field(default_factory=lambda: _id("msg", _next()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "text": self.text,
            "sender": self.sender,
            "recipient": self.recipient,
        }


@dataclass
class Task:
    """An A2A task tracked through its lifecycle."""

    skill: str
    input: str
    requester: str       # who asked (agent id or "operator")
    assignee: str        # agent id doing the work
    id: str = field(default_factory=lambda: _id("task", _next()))
    state: TaskState = "submitted"
    messages: list[Message] = field(default_factory=list)
    result: dict | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "skill": self.skill,
            "input": self.input,
            "requester": self.requester,
            "assignee": self.assignee,
            "state": self.state,
            "messages": [m.to_dict() for m in self.messages],
            "result": self.result,
            "meta": self.meta,
        }
