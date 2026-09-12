# VoyageMind — AI Agentic Travel Planning Workspace

An AI Travel Copilot workspace: AI auto-planning, a manual custom builder, an AI-assisted
builder, a Copilot chat, real-time weather/maps/transport data via a custom Travel MCP
Gateway, budget & route engines, contingency planning, and what-if simulation.

See [PLAN.md](./PLAN.md) for the phased build plan and [docs/architecture.md](./docs/architecture.md)
for the HLD/LLD overview.

## Monorepo layout

```
backend/            FastAPI app (API, agents, services, LLM abstraction)
frontend/           Next.js (App Router, TypeScript) workspace UI
travel-mcp-server/  Custom Travel MCP Gateway (weather, maps, transport, places tools)
docs/               Architecture & design docs
docker-compose.yml  postgres + redis + backend + mcp-server + frontend
```

## Quick start (Docker)

```bash
cp .env.example .env   # fill in keys you have; everything runs without them in demo mode
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (docs at /docs)
- Travel MCP Gateway: http://localhost:8001

## Local development

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (Node 20+)
cd frontend
npm install
npm run dev

# Travel MCP server
cd travel-mcp-server
pip install -e ".[dev]"
uvicorn travel_mcp.server:app --port 8001 --reload
```

## Golden architecture rule

The LLM reasons and decides; it never performs arithmetic or invents live data.
Budget math, route times, weather, and prices come from backend services and MCP tools,and every AI-proposed itinerary change requires explicit user approval.
