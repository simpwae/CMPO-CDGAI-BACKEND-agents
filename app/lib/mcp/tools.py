"""Mock MCP tool servers.

Each tool is a real MCP-style endpoint (name + input schema + handler) but
returns mock data so the protocol wiring is genuine before live integrations
exist. Swap a handler for a real SDK/API call later without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

ToolHandler = Callable[[dict], Awaitable[dict] | dict]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


# --- Mock handlers (deterministic, no Date.now()/random) ---

async def _web_search(args: dict) -> dict:
    q = args.get("query", "")
    return {
        "query": q,
        "results": [
            {"title": f"Result about {q}", "url": "https://example.com/1", "snippet": "..."},
            {"title": f"More on {q}", "url": "https://example.com/2", "snippet": "..."},
        ],
        "_mock": True,
    }


async def _kdp_publish(args: dict) -> dict:
    return {"asin": "B0MOCK1234", "title": args.get("title", "Untitled"),
            "status": "published", "_mock": True}


async def _whatsapp_send(args: dict) -> dict:
    return {"to": args.get("to"), "delivered": True, "message_id": "wamid.MOCK", "_mock": True}


async def _linkedin_post(args: dict) -> dict:
    return {"post_id": "urn:li:share:MOCK", "text": args.get("text", ""),
            "status": "posted", "_mock": True}


async def _email_reply(args: dict) -> dict:
    return {"to": args.get("to"), "subject": args.get("subject", "Re:"),
            "status": "sent", "_mock": True}


async def _events_search(args: dict) -> dict:
    kind = args.get("kind", "hackathon")
    return {
        "kind": kind,
        "events": [
            {"name": "AI Hackathon 2026", "location": "Remote",
             "date": "2026-07-15", "has_dev_component": True, "url": "https://example.com/hack"},
            {"name": "Founders Meetup", "location": "Lahore",
             "date": "2026-07-20", "has_dev_component": False, "url": "https://example.com/meet"},
        ],
        "_mock": True,
    }


async def _github_commit(args: dict) -> dict:
    return {"repo": args.get("repo", "cdg-ai"), "sha": "abc1234",
            "message": args.get("message", "commit"), "_mock": True}


async def _vercel_deploy(args: dict) -> dict:
    return {"project": args.get("project", "cdg-ai"),
            "url": "https://cdg-ai.vercel.app", "state": "READY", "_mock": True}


MOCK_TOOLS: list[ToolSpec] = [
    ToolSpec("web.search", "Search the web",
             {"query": "string"}, _web_search),
    ToolSpec("kdp.publish", "Publish a title to Amazon KDP",
             {"title": "string", "content": "string"}, _kdp_publish),
    ToolSpec("whatsapp.send", "Send a WhatsApp message",
             {"to": "string", "text": "string"}, _whatsapp_send),
    ToolSpec("linkedin.post", "Publish a LinkedIn post",
             {"text": "string"}, _linkedin_post),
    ToolSpec("email.reply", "Reply to an email",
             {"to": "string", "subject": "string", "body": "string"}, _email_reply),
    ToolSpec("events.search", "Search for events / hackathons",
             {"kind": "string"}, _events_search),
    ToolSpec("github.commit", "Commit to a GitHub repo",
             {"repo": "string", "message": "string"}, _github_commit),
    ToolSpec("vercel.deploy", "Deploy a project to Vercel",
             {"project": "string"}, _vercel_deploy),
]
