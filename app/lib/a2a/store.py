"""InMemoryTaskStore — mirrors the @a2a-js/sdk InMemoryTaskStore pattern.

Swappable for a Mongo-backed store later (M6 persists a copy via the event bus).
"""
from __future__ import annotations

from app.lib.a2a.messages import Task


class InMemoryTaskStore:
    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def save(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def all(self) -> list[Task]:
        return list(self._tasks.values())
