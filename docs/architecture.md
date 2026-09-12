# VoyageMind Architecture (HLD → LLD summary)

Full requirements live in the project spec; this is the working reference for contributors.

## High-level design

```
USER → Next.js frontend → FastAPI backend → Agent Orchestrator
    → LLM (reasoning only) ↔ MCP/tools (real external data)
    → Backend business services (deterministic math/validation)
    → PostgreSQL (persistent) + Redis (cache/session)
```

Three user-facing modes:
- **Mode A — AI Auto Plan:** orchestrator pipeline generates a full, editable itinerary.
- **Mode B — Build My Own Trip:** manual timeline builder; every activity is structured data.
- **Mode C — AI Assisted Builder:** user edits, AI detects conflicts and *proposes* fixes
  (Accept / Reject / Edit — never silent mutation).

## Layers & responsibilities

| Layer | Owns | Never does |
|---|---|---|
| Frontend | UI, state, optimistic edits | Secret keys, third-party API calls |
| API layer | Validation, auth, orchestration entry | Business math |
| Agents | Intent, delegation, reasoning over tool output | Arithmetic, inventing prices/times/weather |
| MCP/Tools | Live data: weather, maps, transport, places | LLM-style judgment |
| Services (budget/route/conflict/weather) | Deterministic calculation & validation | Calling the LLM |

## Backend module map (LLD)

```
backend/app/
├── main.py            FastAPI app, middleware, router wiring
├── api/               auth, trips, itinerary, budget, recommendations, optimization, copilot
├── agents/            master, planner, transport, accommodation, places, weather_risk,
│                      budget, route, contingency
├── services/          trip, itinerary, budget, route, weather, optimization, conflict
├── mcp/               client + travel/flight/weather/maps gateways
├── llm/               provider base + gemini/ollama/nova adapters
├── models/            SQLAlchemy entities (users, trips, activities, contingencies, ...)
├── schemas/           Pydantic request/response contracts
├── core/              config, database, security, logging
└── utils/             datetime, geo, currency
```

## Resilience

Every external call: live API → Redis cache → clearly-labeled mock/demo data.
No single provider failure may crash the app; all providers are swappable via config.

## Suggestion protocol

AI changes are structured proposals `{problem, change, reason, impact}` with
Accept / Reject / Edit. On Accept the backend validates, mutates, and recalculates
budget, routes, weather, and conflicts as one cascade.
