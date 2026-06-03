"""MCP HTTP surface: list tools + invoke a tool directly (for testing/ops)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.lib.mcp.client import get_mcp_client

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/tools")
async def list_tools() -> dict:
    return {"tools": get_mcp_client().list_tools()}


class CallBody(BaseModel):
    tool: str
    args: dict = {}
    caller: str = "operator"


@router.post("/call")
async def call_tool(body: CallBody) -> dict:
    try:
        result = await get_mcp_client().call_tool(
            body.tool, body.args, caller=body.caller
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"tool": body.tool, "result": result}
