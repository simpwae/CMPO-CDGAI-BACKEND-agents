"""MCP client: tool listing, calls return mock data, events published, agent wiring."""
from __future__ import annotations

import pytest

from app.lib.events import get_bus
from app.lib.mcp.client import MCPClient
from app.lib.mcp.tools import MOCK_TOOLS


def test_lists_all_eight_tools():
    names = {t["name"] for t in MCPClient().list_tools()}
    assert names == {
        "web.search", "kdp.publish", "whatsapp.send", "linkedin.post",
        "email.reply", "events.search", "github.commit", "vercel.deploy",
    }
    assert len(MOCK_TOOLS) == 8


@pytest.mark.asyncio
async def test_call_returns_mock_data():
    client = MCPClient()
    out = await client.call_tool("events.search", {"kind": "hackathon"})
    assert out["_mock"] is True
    assert any(e["has_dev_component"] for e in out["events"])


@pytest.mark.asyncio
async def test_call_publishes_events():
    bus = get_bus()
    q = bus.subscribe()
    await MCPClient().call_tool("web.search", {"query": "ai"}, caller="zain")
    types = []
    while not q.empty():
        types.append(q.get_nowait().type)
    assert types.count("mcp.tool_call") >= 2  # start + result


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        await MCPClient().call_tool("does.not.exist", {})


@pytest.mark.asyncio
async def test_tool_runner_for_binds_caller():
    client = MCPClient()
    runner = client.tool_runner_for("zain")
    out = await runner("linkedin.post", {"text": "hello"})
    assert out["status"] == "posted"
