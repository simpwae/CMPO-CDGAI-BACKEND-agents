"""Instantiate the roster as live BaseAgent objects and expose a registry."""
from __future__ import annotations

from app.lib.agents.base import BaseAgent
from app.lib.agents.cards import ROSTER

_agents: dict[str, BaseAgent] = {}


def init_agents(*, with_mcp: bool = True) -> dict[str, BaseAgent]:
    """(Re)build the agent registry, wiring each agent its own MCP tool runner."""
    global _agents
    runner_for = None
    if with_mcp:
        from app.lib.mcp.client import get_mcp_client

        client = get_mcp_client()
        runner_for = client.tool_runner_for

    _agents = {
        aid: BaseAgent(card, runner_for(aid) if runner_for else None)
        for aid, card in ROSTER.items()
    }
    return _agents


def all_agents() -> dict[str, BaseAgent]:
    if not _agents:
        init_agents()
    return _agents


def get_agent(agent_id: str) -> BaseAgent:
    return all_agents()[agent_id.lower()]
