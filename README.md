# VoyageMind — AI Agentic Travel Planning Workspace

An AI Travel Copilot workspace: AI auto-planning (Mode A), a manual custom
builder (Mode B), an AI-assisted builder (Mode C) with an approval-first
Copilot, real-time weather/maps/transport data via a custom Travel MCP Gateway,
deterministic budget & route engines, contingency planning, and what-if
simulation.

See [PLAN.md](./PLAN.md) for the phased build plan,
[docs/architecture.md](./docs/architecture.md) for the architecture,
[docs/DEMO.md](./docs/DEMO.md) for the scripted demo, and
[docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for deployment.

## Monorepo layout

```
backend/            FastAPI app (API, agents, services, LLM abstraction)
frontend/           Next.js (App Router, TypeScript) workspace UI
travel-mcp-server/  Custom Travel MCP Gateway (weather, maps, transport, places, FX, web)
scripts/            demo_scenario.py — scripted end-to-end demo (spec §32)
docs/               architecture, demo, deployment docs
docker-compose.yml  postgres + redis + backend + mcp-server + frontend
```

## Quick start (Docker)

```bash
cp .env.example .env   # fill in the keys you have; everything runs without them
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (docs at /docs)
- Travel MCP Gateway: http://localhost:8001

## Quick start (local dev)

```bash
# 1. Travel MCP gateway (demo mode needs no keys)
cd travel-mcp-server && pip install -e ".[dev]"
set TRAVEL_MCP_DEMO_MODE=1 && uvicorn travel_mcp.server:app --port 8001

# 2. Backend
cd ../backend && pip install -e ".[dev]"
uvicorn app.main:app --port 8000

# 3. Frontend
cd ../frontend && npm install && npm run dev
```

Or run the scripted demo (spec §32, all 10 steps): see [docs/DEMO.md](./docs/DEMO.md).

## Where to put your API keys

Copy `.env.example` → `.env` (root, for `docker compose up`) and/or
`backend/.env` (for local backend dev). **The frontend never holds secrets** —
it only needs the public `NEXT_PUBLIC_API_URL`.

| Variable | File | Required | What it does |
|---|---|---|---|
| `GEMINI_API_KEY` | `backend/.env` or root `.env` | for AI features (Modes A/C, Copilot) | Google AI Studio key; free tier works |
| `OPENAI_API_KEY` | same | alternative to Gemini | use with `LLM_PROVIDER=openai` |
| `LLM_PROVIDER` | same | no (default `gemini`) | `gemini` \| `ollama` \| `openai` |
| `JWT_SECRET` | same | **yes in production** | signs auth tokens; use 32+ random chars |
| `DATABASE_URL` | same | no (docker default provided) | PostgreSQL connection string |
| `REDIS_URL` | same | no (optional; cache degrades gracefully) | Redis for API caching |
| `TRAVEL_MCP_URL` | backend `.env` | no (default localhost:8001) | where the backend finds the MCP gateway |
| `DUFFEL_API_KEY` | `travel-mcp-server` env | no — demo flights until set | Duffel test key for real flight offers |
| `TAVILY_API_KEY` | `travel-mcp-server` env | no — search returns "no_provider" until set | web search (closures, events, advisories) |
| `TRAVEL_MCP_DEMO_MODE` | `travel-mcp-server` env | no (`1` = labeled demo data, zero external calls) | demo/CI mode |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | no (default localhost:8000) | backend URL the browser calls |

Weather (Open-Meteo), geocoding, routing (OSRM) and places (OpenStreetMap)
need **no keys at all**. Get a free Gemini key at
https://aistudio.google.com/apikey — set it in `backend/.env` as
`GEMINI_API_KEY=...` and restart the backend.

## Golden architecture rule

The LLM reasons and decides; it never performs arithmetic or invents live data.
Budget math, route times, weather, and prices come from backend services and
MCP tools, and every AI-proposed itinerary change requires explicit user
approval.
