# 🧭 VoyageMind

**An AI travel planning workspace where you and an AI copilot build the trip together.**

VoyageMind isn't another itinerary generator. It's a full workspace that plans, budgets,
stress-tests and continuously watches your trip — with real weather, real road times and
real places — while you stay in control of every single change.

![VoyageMind](docs/screenshot.png)

## What makes it different

Most tools generate a plan and call it done. VoyageMind stays with you through the whole
journey:

- **Three ways to plan** — let the AI plan everything (Mode A), build every day yourself on a
  drag-and-drop timeline (Mode B), or build while the copilot rides shotgun (Mode C).
- **A copilot that asks permission** — it detects schedule conflicts, rain forecasts and
  budget overruns, then *proposes* fixes as cards you accept, reject or edit. It never
  silently edits your trip.
- **Real data, not vibes** — forecasts from Open-Meteo, road times from OSRM, places from
  OpenStreetMap, flights from Duffel — all behind a custom **Travel MCP Gateway** that keeps
  every provider swappable. When a provider is down, you get clearly-labeled demo data
  instead of made-up numbers.
- **A budget engine you can trust** — all money math is deterministic backend logic. The AI
  reasons about it; it never invents it.
- **Contingency planning** — rain, flight delays, hotel issues become structured Plan B/C/D
  fallback trees, not vague paragraphs. Ask *"what if my flight is delayed 3 hours?"* and
  watch the impact chain cascade through check-ins, Day 1, activities and budget.
- **Spending analytics** — a per-trip analysis view (spend per day, biggest expenses,
  category split) plus a global analytics dashboard across all your trips.
- **Group-friendly** — per-traveler preference sliders, overlap/conflict detection, and
  balanced weighting that feeds the planner.

## The workspace

| Area | What you get |
|---|---|
| Dashboard | Trips, budgets, upcoming-trip countdown, spending at a glance |
| Itinerary Builder | Day-by-day timeline, drag & drop, live conflict/warning badges |
| AI Copilot | Context-aware chat with tool calls and approval-first suggestions |
| Budget & Analysis | Category totals, per-day spend, biggest expenses, savings candidates |
| Weather | Multi-day forecast + per-activity risk flags with source labels |
| Map | Every stop pinned, color-coded by day (OpenStreetMap) |
| Risks & Simulate | Schedule risks + "what if…?" simulations with impact chains |
| Contingencies | Structured fallback plans with accept/dismiss/activate lifecycle |
| Group | Balance interests across travelers |

## Tech stack

- **Frontend** — Next.js (App Router) · TypeScript · Tailwind CSS · Sora · Leaflet
- **Backend** — FastAPI · SQLAlchemy 2 · JWT auth · Alembic
- **AI** — pluggable LLM layer (Gemini / OpenAI / Ollama) with a tool-calling agent loop
- **Data** — custom Travel MCP Gateway (MCP protocol) over Open-Meteo · OSRM · Nominatim ·
  Overpass · Duffel · open.er-api
- **Infra** — PostgreSQL (Docker) · Redis (optional, degrades gracefully) · Docker Compose

```
backend/            FastAPI app — API, agents, deterministic services, LLM abstraction
frontend/           Next.js workspace UI
travel-mcp-server/  Travel MCP Gateway — weather, maps, places, transport, FX, search
scripts/            demo_scenario.py — the full demo, scripted over the real API
docs/               architecture, demo runbook, deployment guide
```

## Quick start

```bash
# 0. PostgreSQL (Docker Desktop) — everything is stored here
docker compose up -d postgres redis

# 1. MCP gateway (no keys needed in demo mode)
cd travel-mcp-server && pip install -e ".[dev]"
set TRAVEL_MCP_DEMO_MODE=1 && uvicorn travel_mcp.server:app --port 8001

# 2. Backend — backend/.env already points at postgres://localhost:5432/voyagemind
#    (first run: alembic upgrade head)
cd ../backend && pip install -e ".[dev]"
uvicorn app.main:app --port 8000

# 3. Frontend
cd ../frontend && npm install && npm run dev
```

Open **http://localhost:3000**, create an account, and plan something.

Or with Docker: `cp .env.example .env && docker compose up --build`.
Or run the scripted demo: [docs/DEMO.md](docs/DEMO.md).

## AI features need one key

Everything except the AI copilot works with **zero API keys** (demo data is labeled
as such). To enable AI planning and the copilot, paste a free
[Google AI Studio](https://aistudio.google.com/apikey) key into `backend/.env` as
`GEMINI_API_KEY=...` and restart the backend. All key placement is documented in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Documentation

- [Architecture](docs/architecture.md) — layers, module map, design decisions
- [Demo runbook](docs/DEMO.md) — the 10-step scripted scenario
- [Deployment](docs/DEPLOYMENT.md) — Vercel + Render + Neon guide and key placement
- [Build plan](PLAN.md) — the phased plan the project was built against
