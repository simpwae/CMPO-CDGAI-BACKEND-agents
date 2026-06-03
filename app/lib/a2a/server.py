"""A2AServer — exposes one agent as an A2A peer.

Each server advertises its AgentCard and handles incoming tasks via a single
`handle(task)` entry point (the in-process equivalent of the A2A `message/send`
JSON-RPC method). It drives the task lifecycle and publishes events to the bus
so the dashboard's activity feed reflects every A2A message.
"""
from __future__ import annotations

from app.lib.a2a.messages import Message, Task
from app.lib.agents.base import BaseAgent
from app.lib.events import get_bus


class A2AServer:
    def __init__(self, agent: BaseAgent):
        self.agent = agent

    @property
    def card(self):
        return self.agent.card

    async def handle(self, task: Task) -> Task:
        bus = get_bus()
        task.state = "working"
        await bus.publish(
            "a2a.message",
            {
                "taskId": task.id,
                "skill": task.skill,
                "from": task.requester,
                "to": task.assignee,
                "text": task.input,
                "state": task.state,
            },
        )
        await bus.publish(
            "agent.status", {"agent": self.agent.id, "status": "working"}
        )

        try:
            out = await self.agent.act(task.input, context=task.meta.get("context"))
        except Exception as e:  # noqa: BLE001
            task.state = "failed"
            task.result = {"error": str(e)}
            await bus.publish(
                "agent.status", {"agent": self.agent.id, "status": "error"}
            )
            await bus.publish(
                "a2a.message",
                {"taskId": task.id, "from": self.agent.id,
                 "to": task.requester, "text": f"FAILED: {e}", "state": "failed"},
            )
            return task

        task.messages.append(
            Message(
                role="agent",
                text=out["text"],
                sender=self.agent.id,
                recipient=task.requester,
            )
        )
        task.result = out
        task.state = "completed"

        await bus.publish("agent.status", {"agent": self.agent.id, "status": "idle"})
        await bus.publish(
            "a2a.message",
            {
                "taskId": task.id,
                "from": self.agent.id,
                "to": task.requester,
                "text": out["text"],
                "provider": out["provider"],
                "fallback_used": out["fallback_used"],
                "state": "completed",
            },
        )
        return task
