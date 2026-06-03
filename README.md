# CDGAI — Backend (Agent Runtime)

FastAPI backend for the CDGAI multi-agent operations system. Holds the agent
runtime, the model router, the A2A orchestration layer, the MCP client (tools),
and the AG-UI SSE stream that talks to the operator browser.

Main Agent: **Maryam**. Three-protocol stack: **MCP** (agents → tools),
**A2A** (agent ↔ agent), **AG-UI** (runtime ↔ operator browser).

## Architecture

```
app/
  main.py              FastAPI app + lifespan (recorder, mode rehydrate)
  config.py            env-backed settings
  api/                 HTTP surface
    agents.py          roster + graph for the dashboard
    a2a.py             AgentCard discovery + task dispatch
    mcp.py             list/call MCP tools
    agui.py            SSE stream + approvals + mode toggle
    chat.py            assign objective -> Maryam orchestrates the team
    flows.py           preset flows (events approval / comms via MCP)
    insights.py        appraisals + learning log
  lib/
    llm/               model router: Claude primary -> Gemini fallback
    agents/            roster, AgentCards, base agent (router-only)
    a2a/               in-process orchestration (Maryam as client)
    mcp/               MCP client + 8 mock tool servers
    db/                Mongo (motor) repo + memory fallback + recorder
    agui/              human-in-the-loop approval registry
    conversation.py    Maryam-driven team conversation (real LLM)
    appraiser.py       Hamza performance appraisals
    events.py          process-wide async event bus
    runtime.py         Maryam mode (assist|auto), persisted
```

## Run locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
cp .env.example .env                                      # then fill keys
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

`GET /api/health` reports the live DB backend (`mongo` or `memory`).

## Environment

See `.env.example`. Required for real agent reasoning: `ANTHROPIC_API_KEY`
and/or `GEMINI_API_KEY`. `MONGODB_URI` enables persistent Atlas storage (falls
back to in-memory when unset/unreachable). Never commit `.env`.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

Covers the model-router fallback, roster integrity (no Naseer/Sohaib), A2A
dispatch, MCP tools, the DB layer, AG-UI approvals, Hamza appraisals, the four
flows, and the Maryam-driven objective orchestration.
