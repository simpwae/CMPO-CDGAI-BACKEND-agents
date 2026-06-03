"""MCP client — registers tool servers and dispatches tool calls.

Models the @modelcontextprotocol/sdk client side: a client connects to one or
more tool servers, lists their tools, and calls them by name. Here the servers
are in-process mock endpoints; the call path (list -> call -> normalized result)
is real. Every call is published to the event bus so the dashboard activity feed
shows MCP tool calls live.
"""
from __future__ import annotations

import inspect

from app.lib.events import get_bus
from app.lib.mcp.tools import MOCK_TOOLS, ToolSpec


class MCPClient:
    def __init__(self, tools: list[ToolSpec] | None = None):
        self._tools: dict[str, ToolSpec] = {}
        for spec in tools if tools is not None else MOCK_TOOLS:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in self._tools.values()
        ]

    async def call_tool(self, name: str, args: dict, *, caller: str = "system") -> dict:
        spec = self._tools.get(name)
        bus = get_bus()
        if spec is None:
            await bus.publish(
                "mcp.tool_call",
                {"tool": name, "caller": caller, "ok": False, "error": "unknown tool"},
            )
            raise KeyError(f"unknown MCP tool '{name}'")

        await bus.publish(
            "mcp.tool_call",
            {"tool": name, "caller": caller, "args": args, "ok": True, "phase": "start"},
        )
        out = spec.handler(args)
        if inspect.isawaitable(out):
            out = await out
        await bus.publish(
            "mcp.tool_call",
            {"tool": name, "caller": caller, "ok": True, "phase": "result", "result": out},
        )
        return out


    def tool_runner_for(self, caller: str):
        """Return a (tool, args) -> result runner bound to a caller (an agent)."""
        async def runner(tool: str, args: dict) -> dict:
            return await self.call_tool(tool, args, caller=caller)

        return runner


_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
