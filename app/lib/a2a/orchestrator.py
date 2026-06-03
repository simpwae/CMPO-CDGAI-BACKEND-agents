"""Orchestrator — Maryam acting as the A2A client that routes tasks to peers.

Holds the transport, the task store, and a registry of A2A servers (one per
agent). `dispatch()` is the single primitive flows build on; `discover()`
returns AgentCards just like an A2A client browsing peers by card.
"""
from __future__ import annotations

from app.lib.a2a.messages import Task
from app.lib.a2a.server import A2AServer
from app.lib.a2a.store import InMemoryTaskStore
from app.lib.a2a.transport import InProcessTransport
from app.lib.agents.cards import list_cards
from app.lib.agents.roster import all_agents


class Orchestrator:
    def __init__(self):
        self.transport = InProcessTransport()
        self.store = InMemoryTaskStore()
        self.servers: dict[str, A2AServer] = {}
        self._register_all()

    def _register_all(self) -> None:
        for agent_id, agent in all_agents().items():
            server = A2AServer(agent)
            self.servers[agent_id] = server
            self.transport.register(agent_id, server)

    def discover(self) -> list[dict]:
        """Browse peers by AgentCard (A2A discovery)."""
        return [c.to_dict() for c in list_cards()]

    async def dispatch(
        self,
        *,
        skill: str,
        input: str,
        assignee: str,
        requester: str = "maryam",
        context: str | None = None,
    ) -> Task:
        task = Task(
            skill=skill,
            input=input,
            requester=requester,
            assignee=assignee,
            meta={"context": context} if context else {},
        )
        self.store.save(task)
        task = await self.transport.send(assignee, task)
        self.store.save(task)
        return task


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
