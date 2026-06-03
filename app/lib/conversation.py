"""Hierarchical, cascading team orchestration (real LLM).

The operator assigns an objective. Maryam does NOT get a scripted plan — she
(real LLM) decides which of her direct reports to tag and what to ask each.
Each tagged report then makes ITS OWN decision the same way, cascading down the
org chart until the work reaches the specialist who does it:

    Maryam → Momin → Naqash → Shams (backend) / Fateh (frontend) / Usman (devops)
                                     ↘ Ihsan (test)

So tagging Momin with build work makes Momin autonomously route to Naqash, who
assigns the right engineer — no hard-coded path, every hop is a real decision.
Every message is directed (sender + `to`) and persisted, so the dashboard shows
exactly who talked to whom. Managers reason on the lead model tier.
"""
from __future__ import annotations

import json

from app.lib.agents.cards import ROSTER, get_card
from app.lib.appraiser import Outcome, appraise
from app.lib.db.factory import get_repo
from app.lib.events import get_bus
from app.lib.llm.router import get_router
from app.lib.llm.types import LLMMessage
from app.lib.workspace import new_project, write_file

# Org chart: manager -> direct reports (everyone else is a leaf who does the work).
HIERARCHY: dict[str, list[str]] = {
    "maryam": ["tariq", "momin", "zain", "hamza"],
    "momin": ["naqash"],
    "naqash": ["fateh", "shams", "usman", "ihsan"],
}
MAX_DEPTH = 4
MAX_ASKS = 3


def _name(agent_id: str) -> str:
    c = ROSTER.get(agent_id)
    return c.name if c else agent_id.title()


def _reports_blurb(reports: list[str]) -> str:
    return "\n".join(f"- {r} ({_name(r)} — {get_card(r).role})" for r in reports)


async def _history(limit: int = 60) -> list[dict]:
    repo = await get_repo()
    # Fetch the most recent `limit` messages, then return them in chronological
    # order (oldest -> newest). Sorting ascending would return the OLDEST messages
    # once the thread grows past `limit`, hiding new replies.
    rows = await repo.find("messages", {"thread": "main"}, limit=limit, sort_desc=True)
    return list(reversed(rows))


def _thread_text(history: list[dict]) -> str:
    if not history:
        return "(conversation just started)"
    out = []
    for m in history:
        to = f" → {m['to_name']}" if m.get("to_name") else ""
        out.append(f"{m.get('name', m['sender'])}{to}: {m['text']}")
    return "\n".join(out)


async def _post(sender: str, text: str, *, to: str | None = None,
                provider: str | None = None, fallback_used: bool = False,
                name: str | None = None) -> dict:
    repo = await get_repo()
    doc = {
        "thread": "main",
        "sender": sender,
        "name": name or _name(sender),
        "to": to,
        "to_name": _name(to) if to and to in ROSTER else (to.title() if to else None),
        "text": text,
        "provider": provider,
        "fallback_used": fallback_used,
    }
    await repo.insert("messages", doc)
    bus = get_bus()
    await bus.publish("chat.message", doc)
    if sender in ROSTER:
        await bus.publish("agent.status", {"agent": sender, "status": "idle"})
    if to and to in ROSTER:
        await bus.publish(
            "a2a.message", {"from": sender, "to": to, "text": text, "state": "completed"}
        )
    return doc


# Agents that produce real code when assigned work (and what they build).
DEV_AGENTS = {
    "fateh": "frontend",
    "shams": "backend",
    "usman": "devops/infra",
    "ihsan": "tests",
}


async def _reply(agent_id: str, directive: str, *, asker: str, project: str) -> None:
    """A leaf agent does the work. Developers actually write a multi-file project
    to disk; everyone else replies in prose."""
    if agent_id in DEV_AGENTS:
        await _dev_work(agent_id, directive, asker=asker, project=project)
        return

    await get_bus().publish("agent.status", {"agent": agent_id, "status": "working"})
    history = await _history()
    user = (
        f"Team conversation so far:\n{_thread_text(history)}\n\n"
        f"{_name(asker)} assigned you: \"{directive}\"\n"
        "Reply in 1-3 sentences as yourself, actually doing your part of the work."
    )
    res = await get_router().generate(
        agent_id, [LLMMessage(role="user", content=user)],
        system=get_card(agent_id).system_prompt, max_tokens=350,
    )
    await _post(agent_id, res.text, to=asker,
                provider=res.provider, fallback_used=res.fallback_used)


async def _dev_work(agent_id: str, directive: str, *, asker: str, project: str) -> None:
    """A developer does REAL coding: the LLM emits a multi-file project, each file
    is written to disk under the project workspace AND published as an artifact so
    the dashboard shows the file tree."""
    await get_bus().publish("agent.status", {"agent": agent_id, "status": "working"})
    area = DEV_AGENTS[agent_id]
    system = (
        get_card(agent_id).system_prompt
        + f"\n\nYou are a real {area} engineer. When assigned work, BUILD A REAL "
        "PROJECT now — multiple complete, runnable files with a sensible folder "
        "structure. Respond with: a one-sentence note, then 2-5 fenced code blocks. "
        "Each block's info string MUST be the language and the full file path, e.g.\n"
        "```python backend/app/main.py\n...code...\n```\n"
        "Give complete file contents (not snippets). Use real directories in the paths."
    )
    history = await _history()
    user = (
        f"Team conversation so far:\n{_thread_text(history)}\n\n"
        f"{_name(asker)} assigned you: \"{directive}\"\n"
        f"Build the {area} part of the project now as real files."
    )
    res = await get_router().generate(
        agent_id, [LLMMessage(role="user", content=user)],
        system=system, max_tokens=2200, temperature=0.4,
    )
    note, files = _extract_files(res.text, agent_id)

    await _post(agent_id, note, to=asker,
                provider=res.provider, fallback_used=res.fallback_used)

    for language, path, code in files:
        disk_path = write_file(project, path, code)
        await get_bus().publish("artifact", {
            "agent": agent_id, "name": _name(agent_id), "area": area,
            "project": project, "filename": path, "language": language,
            "code": code, "note": note, "provider": res.provider,
            "written": bool(disk_path),
        })


_EXT = {"python": "py", "typescript": "ts", "javascript": "js", "tsx": "tsx",
        "jsx": "jsx", "json": "json", "yaml": "yml", "yml": "yml",
        "dockerfile": "Dockerfile", "bash": "sh", "sh": "sh", "html": "html",
        "css": "css", "sql": "sql", "markdown": "md", "text": "txt"}


def _extract_files(text: str, agent_id: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Pull (note, [(language, path, content), ...]) from fenced code blocks."""
    import re

    blocks = re.findall(r"```([^\n`]*)\n(.*?)```", text, re.DOTALL)
    files: list[tuple[str, str, str]] = []
    for i, (info, code) in enumerate(blocks):
        parts = info.strip().split()
        language = parts[0] if parts else "text"
        path = next((t for t in parts[1:] if "." in t or "/" in t), "")
        if not path:
            ext = _EXT.get(language.lower(), "txt")
            path = f"{DEV_AGENTS.get(agent_id, 'src')}/file{i + 1}.{ext}"
        files.append((language, path.strip(), code.strip()))

    first = text.index("```") if "```" in text else len(text)
    note = text[:first].strip() or (
        f"Built {len(files)} file(s)." if files else "Working on it."
    )
    return note, files


async def _plan(manager_id: str, directive: str, reports: list[str]) -> dict:
    """A manager decides which reports to tag and what to ask each (real LLM)."""
    await get_bus().publish("agent.status", {"agent": manager_id, "status": "working"})
    history = await _history()
    system = (
        get_card(manager_id).system_prompt
        + "\n\nYour direct reports:\n" + _reports_blurb(reports)
        + "\n\nRoute the task to the report(s) whose role fits, using this mapping: "
        "research → Tariq; building/developing/implementing software, an API, app "
        "or feature → Momin (he manages the dev team); events/hackathons/outreach/"
        "LinkedIn/email → Zain; performance review → Hamza; general development → "
        "Naqash; backend → Shams; frontend → Fateh; devops/deploy → Usman; "
        "testing/QA → Ihsan. Respond ONLY as JSON: "
        '{"summary": "<1 sentence acknowledging the task>", '
        '"asks": [{"agent": "<report_id>", "question": "<what you assign them>"}]}. '
        "Use only ids from your direct reports. Keep each question to one sentence."
    )
    user = (
        f"Conversation so far:\n{_thread_text(history)}\n\n"
        f"You were asked: \"{directive}\"\nDecide who to delegate to."
    )
    res = await get_router().generate(
        manager_id, [LLMMessage(role="user", content=user)],
        system=system, max_tokens=400, temperature=0.3,
    )
    parsed = _parse_plan(res.text, reports)
    _ensure_dev_routing(manager_id, directive, parsed, reports)
    parsed["_provider"] = res.provider
    parsed["_fallback"] = res.fallback_used
    return parsed


def _parse_plan(text: str, reports: list[str]) -> dict:
    import re

    cleaned = re.sub(r"```(?:json)?", "", text)
    # First try strict JSON.
    try:
        data = json.loads(cleaned[cleaned.index("{"): cleaned.rindex("}") + 1])
        asks = [
            {"agent": a["agent"], "question": str(a.get("question", "")).strip()
             or "Please handle this."}
            for a in data.get("asks", [])
            if a.get("agent") in reports
        ][:MAX_ASKS]
        summary = str(data.get("summary", "")).strip()
        if summary and asks:
            return {"summary": summary, "asks": asks}
        if summary and not asks:
            return {"summary": summary,
                    "asks": [{"agent": reports[0], "question": "Please take this on."}]}
    except Exception:
        pass

    # Fallback: regex-extract fields (handles truncated/loose JSON without leaking it).
    summ = re.search(r'"summary"\s*:\s*"([^"]+)"', cleaned)
    agents = re.findall(r'"agent"\s*:\s*"(\w+)"', cleaned)
    qs = re.findall(r'"question"\s*:\s*"([^"]+)"', cleaned)
    asks = [
        {"agent": a, "question": qs[i] if i < len(qs) else "Please handle this."}
        for i, a in enumerate(agents) if a in reports
    ][:MAX_ASKS]
    if not asks:
        asks = [{"agent": reports[0], "question": "Please take this on."}]
    summary = (summ.group(1) if summ else "On it — delegating now.").strip()
    return {"summary": summary, "asks": asks}


_DEV_KW = ("build", "develop", "implement", "api", "backend", "frontend",
           "code", "app", "feature", "deploy", "devops", "test")


def _ensure_dev_routing(manager_id: str, directive: str, parsed: dict,
                        reports: list[str]) -> None:
    """Safety net so build orders always reach the dev team (the cascade the
    user expects): Momin -> Naqash, and Naqash -> the right specialist."""
    d = directive.lower()
    if not any(k in d for k in _DEV_KW):
        return
    have = {a["agent"] for a in parsed["asks"]}
    if "naqash" in reports and "naqash" not in have:
        parsed["asks"].insert(
            0, {"agent": "naqash", "question": f"Please lead development for: {directive}"}
        )
    if manager_id == "naqash":
        pick = ("shams" if ("backend" in d or "api" in d)
                else "fateh" if "frontend" in d
                else "usman" if ("deploy" in d or "devops" in d)
                else "shams")
        if pick in reports and pick not in have:
            parsed["asks"].insert(0, {"agent": pick, "question": f"Please handle: {directive}"})


def parse_mention(text: str) -> tuple[str | None, str]:
    """Pull a leading/embedded @mention and resolve it to an agent id.

    "@momin build the API" -> ("momin", "build the API"). Matches agent ids and
    first names case-insensitively.
    """
    import re

    by_first = {c.name.split()[0].lower(): aid for aid, c in ROSTER.items()}
    for m in re.finditer(r"@([A-Za-z]+)", text):
        token = m.group(1).lower()
        target = token if token in ROSTER else by_first.get(token)
        if target:
            cleaned = (text[: m.start()] + text[m.end():]).strip()
            return target, cleaned or text
    return None, text


async def _delegate(agent_id: str, directive: str, *, asker: str,
                    involved: set[str], depth: int, project: str) -> None:
    """Recursively walk the hierarchy: managers delegate, leaves do the work."""
    involved.add(agent_id)
    reports = HIERARCHY.get(agent_id)
    if not reports or depth >= MAX_DEPTH:
        await _reply(agent_id, directive, asker=asker, project=project)
        return

    plan = await _plan(agent_id, directive, reports)
    await _post(agent_id, plan["summary"], to=asker,
                provider=plan["_provider"], fallback_used=plan["_fallback"])
    for ask in plan["asks"]:
        rid = ask["agent"]
        await _post(agent_id, ask["question"], to=rid)
        await _delegate(rid, ask["question"], asker=agent_id,
                        involved=involved, depth=depth + 1, project=project)


async def run_order(text: str, to: str | None = None) -> dict:
    """The human IS Maryam: she gives an order and tags a teammate (@name).

    Maryam's message is posted as herself, then the tagged teammate's branch
    cascades autonomously (managers delegate down, the specialist does the work).
    """
    target, order = (to, text) if to else parse_mention(text)
    # Maryam (the primary user) speaks.
    await _post("maryam", order, to=target, name="Maryam")

    involved: set[str] = set()
    if not target or target not in ROSTER:
        # No one tagged — Maryam is addressing the room; nothing to cascade.
        return {"involved": []}

    project = new_project(order)
    try:
        await _delegate(target, order, asker="maryam", involved=involved,
                        depth=1, project=project)
        outcomes = [Outcome(agent=a, success=True) for a in involved if a != "hamza"]
        if outcomes:
            await appraise(outcomes)
    except Exception as e:  # noqa: BLE001
        await get_bus().publish("agent.status", {"agent": target, "status": "error"})
        await _post(
            target,
            f"⚠️ I couldn't reach a language model ({type(e).__name__}). Configure a "
            "working LLM key (GROQ_API_KEY / ANTHROPIC_API_KEY) and retry.",
            to="maryam",
        )
    return {"involved": sorted(involved), "project": project}


async def get_thread(limit: int = 60) -> list[dict]:
    return await _history(limit)
