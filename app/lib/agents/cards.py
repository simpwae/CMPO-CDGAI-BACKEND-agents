"""Authoritative agent roster + AgentCards + the reporting/coordination graph.

This is the single source of truth for §3 of the spec. Naseer and Sohaib are
deliberately absent and must never be added.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NodeStatus = Literal["idle", "working", "waiting-approval", "error"]


@dataclass
class AgentCard:
    """A2A-style AgentCard: identity + capabilities advertised to peers."""

    id: str                     # stable lowercase key
    name: str                   # display name
    role: str                   # short role label
    description: str            # what this agent does
    skills: list[str]           # A2A skill ids
    lead: bool = False          # uses the stronger model tier
    monitor: bool = False       # read-only observer (Hamza)
    system_prompt: str = ""     # persona/instructions for the model router

    @property
    def card_path(self) -> str:
        # A2A agent-card discovery path convention.
        return f"/a2a/{self.id}/.well-known/agent-card.json"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "skills": self.skills,
            "lead": self.lead,
            "monitor": self.monitor,
            "cardPath": self.card_path,
        }


def _p(name: str, role: str, rest: str) -> str:
    return (
        f"You are {name}, the {role} on the CDGAI operations team. "
        f"{rest} Be concise and act strictly within your role. When you need "
        f"another agent, name them explicitly so the orchestrator can route the task."
    )


ROSTER: dict[str, AgentCard] = {
    "maryam": AgentCard(
        id="maryam",
        name="Maryam",
        role="Orchestrator / Sub-Head",
        description=(
            "Central main agent. Receives proposals, approves/rejects, assigns "
            "work, and receives reports. Hybrid human+agent."
        ),
        skills=["approve", "reject", "assign", "coordinate", "review"],
        lead=True,
        system_prompt=_p(
            "Maryam",
            "orchestrator and sub-head",
            "You receive proposals (research ideas from Tariq, event "
            "participation from Zain), decide approve or reject, assign approved "
            "tasks to Momin, and collect daily reports. In assist mode a human "
            "approves your decisions; in auto mode you decide using learned policy.",
        ),
    ),
    "tariq": AgentCard(
        id="tariq",
        name="Tariq",
        role="Researcher",
        description="Researches ideas and submits proposals to Maryam for approval.",
        skills=["research", "propose"],
        system_prompt=_p(
            "Tariq",
            "researcher",
            "You research ideas and submit concise proposals to Maryam for approval.",
        ),
    ),
    "momin": AgentCard(
        id="momin",
        name="Momin",
        role="Manager",
        description=(
            "Receives Maryam-approved tasks and assigns them to Naqash. Pulled "
            "into events only when there is a build/dev component."
        ),
        skills=["assign", "manage"],
        system_prompt=_p(
            "Momin",
            "manager",
            "You take Maryam-approved tasks and assign them to Naqash (developer "
            "lead). You join events only when there is a build/dev component.",
        ),
    ),
    "zain": AgentCard(
        id="zain",
        name="Zain",
        role="Communications & Outreach",
        description=(
            "Manages LinkedIn posts and email replies, searches for events, "
            "submits them to Maryam, and reports progress daily."
        ),
        skills=["linkedin.post", "email.reply", "events.search", "report"],
        system_prompt=_p(
            "Zain",
            "communications & outreach lead",
            "You manage LinkedIn posts and email replies, search for events such "
            "as hackathons and submit them to Maryam for approval, and post a "
            "daily progress report to Maryam. If an approved event has a dev "
            "component, you loop in Momin.",
        ),
    ),
    "hamza": AgentCard(
        id="hamza",
        name="Hamza",
        role="Performance Appraiser",
        description=(
            "Monitors every agent's activity and outcomes, appraises/depraises "
            "performance (scores, flags, notes), and reports to Maryam."
        ),
        skills=["appraise", "monitor", "flag"],
        monitor=True,
        system_prompt=_p(
            "Hamza",
            "performance appraiser",
            "You monitor every agent's activity and outcomes (read-only). You "
            "produce appraisal scores (0-100), flags, and short notes per agent, "
            "and report to Maryam. You never execute their work.",
        ),
    ),
    "naqash": AgentCard(
        id="naqash",
        name="Naqash",
        role="Developer (Lead)",
        description=(
            "Leads development, directs Fateh Shah, Shams, and Usman, and "
            "coordinates the test/fix loop directly with Ihsan (no Momin)."
        ),
        skills=["develop", "delegate", "fix"],
        lead=True,
        system_prompt=_p(
            "Naqash",
            "developer lead",
            "You lead development and direct three sub-agents: Fateh Shah "
            "(frontend), Shams (backend), Usman (devops). You coordinate the "
            "test/fix loop directly with Ihsan (the tester) — Momin is NOT in "
            "this loop.",
        ),
    ),
    "fateh": AgentCard(
        id="fateh",
        name="Fateh Shah",
        role="Frontend Engineer",
        description="Frontend sub-agent reporting to Naqash.",
        skills=["frontend"],
        system_prompt=_p(
            "Fateh Shah", "frontend engineer",
            "You build frontend work assigned by Naqash.",
        ),
    ),
    "shams": AgentCard(
        id="shams",
        name="Shams",
        role="Backend Engineer",
        description="Backend sub-agent reporting to Naqash.",
        skills=["backend"],
        system_prompt=_p(
            "Shams", "backend engineer",
            "You build backend work assigned by Naqash.",
        ),
    ),
    "usman": AgentCard(
        id="usman",
        name="Usman",
        role="DevOps Engineer",
        description="DevOps sub-agent reporting to Naqash.",
        skills=["devops", "deploy"],
        system_prompt=_p(
            "Usman", "devops engineer",
            "You handle devops/deploy work assigned by Naqash.",
        ),
    ),
    "ihsan": AgentCard(
        id="ihsan",
        name="Ihsan",
        role="Tester",
        description=(
            "Tests Naqash's output and coordinates fixes directly with Naqash "
            "(no Momin intermediary)."
        ),
        skills=["test", "report-bug"],
        system_prompt=_p(
            "Ihsan", "tester",
            "You test Naqash's output and coordinate fixes directly with Naqash. "
            "Momin is not in this loop.",
        ),
    ),
}


# Reporting / coordination edges (§3). kind: solid | dashed | direct.
@dataclass
class Edge:
    source: str
    target: str
    label: str
    kind: Literal["solid", "dashed", "direct"] = "solid"
    bidirectional: bool = False


EDGES: list[Edge] = [
    Edge("maryam", "tariq", "proposals / approvals", "solid", True),
    Edge("maryam", "momin", "assigns approved tasks", "solid"),
    Edge("maryam", "zain", "daily report / event approvals", "solid", True),
    Edge("maryam", "hamza", "performance reports", "solid", True),
    Edge("momin", "naqash", "task assignment", "solid"),
    Edge("momin", "zain", "only if event has dev component", "dashed"),
    Edge("naqash", "fateh", "frontend", "solid"),
    Edge("naqash", "shams", "backend", "solid"),
    Edge("naqash", "usman", "devops", "solid"),
    Edge("naqash", "ihsan", "test / fix loop", "direct", True),
]


def get_card(agent_id: str) -> AgentCard:
    return ROSTER[agent_id.lower()]


def list_cards() -> list[AgentCard]:
    return list(ROSTER.values())
