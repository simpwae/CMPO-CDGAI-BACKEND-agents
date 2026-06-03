"""Human-in-the-loop approval registry (the AG-UI HITL primitive).

A flow calls `request(...)` and awaits the returned future. In `assist` mode the
request is surfaced to the operator browser (via an "approval.request" bus event)
and the future resolves when the operator POSTs a decision. In `auto` mode agent
Maryam auto-approves immediately using the learned policy, and the decision is
still recorded for transparency.

Every resolved decision is published as a "decision" event (persisted to the
decisions collection) and, in assist mode, as a "learning" event so agent Maryam
accrues training data from human Maryam.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.lib.events import get_bus
from app.lib.runtime import get_mode

_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"approval-{_counter:06d}"


@dataclass
class PendingApproval:
    id: str
    title: str
    detail: str
    requester: str            # agent id that needs the decision
    kind: str                 # "idea" | "event" | ...
    context: dict[str, Any] = field(default_factory=dict)
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "detail": self.detail,
            "requester": self.requester,
            "kind": self.kind,
            "context": self.context,
        }


class ApprovalRegistry:
    def __init__(self):
        self._pending: dict[str, PendingApproval] = {}

    def pending(self) -> list[dict]:
        return [p.to_dict() for p in self._pending.values()]

    async def request(
        self, *, title: str, detail: str, requester: str, kind: str, context: dict | None = None
    ) -> dict:
        """Create an approval and wait for the decision. Returns the decision dict."""
        bus = get_bus()
        mode = get_mode()
        approval = PendingApproval(
            id=_next_id(), title=title, detail=detail,
            requester=requester, kind=kind, context=context or {},
        )
        self._pending[approval.id] = approval

        await bus.publish(
            "approval.request",
            {**approval.to_dict(), "mode": mode},
        )

        if mode == "auto":
            # Agent Maryam decides autonomously (MVP policy: approve).
            await self.resolve(approval.id, approved=True, by="agent-maryam", auto=True)

        decision = await approval.future
        return decision

    async def resolve(
        self, approval_id: str, *, approved: bool, by: str = "operator", auto: bool = False
    ) -> dict:
        approval = self._pending.pop(approval_id, None)
        if approval is None:
            raise KeyError(f"unknown approval '{approval_id}'")

        bus = get_bus()
        decision = {
            "approval_id": approval_id,
            "kind": approval.kind,
            "requester": approval.requester,
            "title": approval.title,
            "approved": approved,
            "by": by,
            "auto": auto,
            "context": approval.context,
        }
        if not approval.future.done():
            approval.future.set_result(decision)

        await bus.publish("decision", decision)
        # In assist mode, every human decision becomes learning data for Maryam.
        if not auto:
            await bus.publish("learning", {**decision, "source": "human-maryam"})
        return decision


_registry: ApprovalRegistry | None = None


def get_approvals() -> ApprovalRegistry:
    global _registry
    if _registry is None:
        _registry = ApprovalRegistry()
    return _registry
