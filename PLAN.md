# VoyageMind — AI Agentic Travel Planning Workspace · Master Plan

A production-quality prototype of an **AI Travel Copilot workspace** (not just an itinerary generator), built per the HLD/LLD spec.

**Stack:** Next.js frontend · FastAPI backend · PostgreSQL + Redis · Custom Travel MCP Gateway · Pluggable LLM providers (Gemini/Ollama/OpenAI/Nova-ready)

**Golden rule (never violate):** LLM = reasoning only. All arithmetic, validation, routes, weather, and prices come from backend services / MCP tools / real APIs. The user always approves AI-proposed changes.

---

## Progress Legend
- [ ] Not started · [~] In progress · [x] Done

---

## Phase 0 — Project Scaffolding ✅ (verified: backend boots & 6/6 tests pass, MCP gateway boots, frontend builds)
- [x] 0.1 Monorepo layout: `backend/`, `frontend/`, `travel-mcp-server/`, `docs/`, `docker-compose.yml`
- [x] 0.2 `docker-compose.yml` with PostgreSQL, Redis, backend, frontend, mcp-server
- [x] 0.3 Backend scaffold: FastAPI `app/main.py`, `core/config.py` (pydantic-settings, env vars), `core/database.py`, `core/logging.py` (structured logs w/ request IDs), `core/security.py`
- [x] 0.4 Frontend scaffold: Next.js App Router + TypeScript, `components/ services/ hooks/ types/ utils/` folders
- [x] 0.5 `.env.example` for all keys (Gemini/OpenAI, Open-Meteo, Mapbox/OSM, Duffel); secrets never reach frontend
- [x] 0.6 CI script: lint + pytest + frontend build

## Phase 1 — Foundation (Domain Models & Trip CRUD) ✅ (30/30 tests pass, e2e smoke verified over HTTP)
- [x] 1.1 SQLAlchemy models per spec §21: `users, trips, trip_preferences, itinerary_days, activities, transport_options, accommodations, recommendations, contingencies, weather_snapshots, budget_items, trip_events, copilot_messages` + Alembic migrations (initial revision generated & verified)
- [x] 1.2 Pydantic schemas: `trip_schema, itinerary_schema, activity_schema, budget_schema`
- [x] 1.3 Activity model with full fields (`id, day, name, category, location, lat, lng, start/end_time, duration, estimated_cost, weather_sensitive, indoor, source, user_selected, ai_recommended, confidence`)
- [x] 1.4 Auth: register/login (JWT), per-user trip ownership enforced on every trip route (404 on foreign access)
- [x] 1.5 Trip APIs: `POST/GET/PUT/DELETE /trips`, `GET /trips/{trip_id}` — trip inputs (origin, destination, dates, travelers, budget, currency, preferences, constraints); auto-creates one `itinerary_days` row per trip date
- [x] 1.6 LLM abstraction layer: `llm/provider.py` (`generate`, `generate_structured`, `call_tools`) + `GeminiProvider`, `OllamaProvider`, `OpenAIProvider` (+ Nova adapter stub). Provider chosen by config (MCP SDK 2.x `MCPServer` used for the gateway)
- [x] 1.7 Redis client + cache helper with TTLs, graceful no-op degradation when Redis is down (rate limiting lands with hardening in Phase 8)
- [x] 1.8 Unit tests: models, schemas, auth, trip CRUD, LLM providers (30 tests)

## Phase 2 — Itinerary Engine & Custom Builder (Mode B) ✅ (49/49 backend tests; e2e HTTP smoke verified; frontend builds & lints clean)
- [x] 2.1 `services/itinerary_service.py`: `add_activity, update_activity, move_activity, delete_activity, reorder_day, validate_itinerary` (mutations always budget-synced; derived end_time from start+duration)
- [x] 2.2 `services/budget_service.py`: deterministic totals per category; under/near/over/unknown states; activity costs auto-mirror into budget lines (source_ref `activity:<id>`); arithmetic never touches the LLM
- [x] 2.3 `services/conflict_service.py`: overlap + end-before-start conflicts, labeled `heuristic_transfer_buffer` warnings between distant stops (real routing arrives with Maps MCP in Phase 3/4)
- [x] 2.4 APIs: `POST /trips/{id}/activities`, `PUT/DELETE /activities/{id}`, `POST /activities/{id}/move`, `POST /trips/{id}/days/{day_id}/reorder`, `GET/POST /trips/{id}/budget`, `DELETE /budget-items/{id}`, `POST /trips/{id}/check-conflicts`, `GET /trips/{id}/itinerary` — all ownership-enforced
- [x] 2.5 Frontend TripForm (origin/destination, dates, travelers, budget, currency, style, interest tags, constraints)
- [x] 2.6 Timeline: day columns with per-day conflict/warning badges, Add dialog (categories, time, duration, cost, weather flags), delete
- [x] 2.7 Drag & drop: reorder within a day (position column + reorder API) and move between days; backend-validated on drop
- [x] 2.8 ActivityCard with visual indicators (✓/⚠/✕/🤖/👤/🌦/💰)
- [x] 2.9 BudgetDashboard (spent / remaining / per-category bars / state badge)
- [x] 2.10 Map component (Leaflet + OpenStreetMap) with per-day colored pins
- [x] 2.11 Unit tests: budget math & states, conflict detection, itinerary mutations, API integration incl. cross-user denial (19 new tests)

## Phase 3 — Travel MCP Gateway & External Data ✅ (gateway 15/15 + backend 63/63 tests; MCP protocol round-trip verified over HTTP; e2e weather smoke through demo-mode gateway)
- [x] 3.1 `travel-mcp-server/` (MCP 2.x `MCPServer`, streamable-HTTP, stateless) + backend `mcp/client.py` speaking the real MCP protocol (initialize → call_tool, structured-content unwrap, degrade-to-`unavailable`)
- [x] 3.2 Weather MCP (Open-Meteo): current + multi-day forecast, rain probability, precipitation, WMO rain-code flagging, best-effort air quality (US AQI); honest note that the provider has no severe-alert feed
- [x] 3.3 Maps MCP: geocoding (Open-Meteo geocoder), `calculate_route` with real road distance/duration (OSRM), `search_places` (Nominatim), `find_nearby_places` (Overpass, 7 categories), `get_place_details` (Nominatim lookup)
- [x] 3.4 Flight/Transport MCP: Duffel offer search when `DUFFEL_API_KEY` set, clearly-labeled demo offers otherwise; provider isolated behind the tool interface
- [x] 3.5 `search_stays`: provider-replaceable interface with labeled demo stays until a stays provider is integrated
- [x] 3.6 Currency tool (open.er-api.com) — failures return `unavailable`, never a fabricated rate
- [x] 3.7 Web search tool: Tavily-compatible when `TAVILY_API_KEY` set; otherwise honest `no_provider` (results are never fabricated)
- [x] 3.8 Gateway = one clean domain tool surface (11 tools incl. `ping`); third-party endpoints hidden from agents
- [x] 3.9 Resilience: every tool catches provider failures into structured errors; `TRAVEL_MCP_DEMO_MODE=1` serves labeled demo data with zero external calls; backends degrade live → cache → labeled mock
- [x] 3.10 Redis caching by data type: weather 30 min, geocode/places 24 h–7 d, routes 24 h, nearby 6 h, transport 15 min, stays 6 h, FX 24 h; volatile web search never cached; mocks never cached
- [x] 3.11 Source transparency: every response carries `{source, retrieved_at, is_mock}` (+ `cached` flag on cache hits), surfaced through APIs
- [x] 3.12 Tests: gateway tools vs mocked HTTP (15), real MCP protocol round-trip vs in-process uvicorn gateway, gateway-down degradation, facade cache/fallbacks, weather API incl. geocode write-back (63 backend tests total)

## Phase 4 — Business Logic Services (Deterministic Core) ✅ (95/95 backend tests; full-stack HTTP smoke through demo gateway)
- [x] 4.1 `services/route_service.py`: per-day route reports via real routing (OSRM through Maps MCP; new gateway `optimize_route` tool on the OSRM trip service); before/after travel-time savings (`saved_minutes`), suggested order ids, `already_optimal` flag; labeled nearest-neighbor heuristic when routing is down. Reports only — applying a reorder stays with the user
- [x] 4.2 `services/weather_service.py`: deterministic thresholds — rain (probability ≥60% / ≥5 mm / provider significant-rain flag), heat (≥38 °C), severe alerts override; per-day risk + affected weather-sensitive outdoor activity ids + rule-based suggestions; date-then-positional forecast matching (works with demo dates)
- [x] 4.3 `services/optimization_service.py`: `optimize_itinerary` (route + conflict report), `optimize_day`, deterministic `budget_savings_plan` — same-category median candidates, greedy coverage of the shortfall, largest-lines review list; `utils/currency_utils.py` (convert, exact-sum proportional allocation)
- [x] 4.4 `utils/`: datetime (parse/format/gap, invalid-input safe), geo (haversine), currency helpers
- [x] 4.5 APIs: `POST /trips/{id}/optimize-route` (whole trip or `day_id`), `/optimize-budget`, `/check-weather` — all ownership-enforced
- [x] 4.6 Unit tests: route optimization & heuristic fallback, weather thresholds (rain/heat/severe/unresolved), budget plan medians & coverage, date/time edge cases, currency rounding, API integration + cross-user denial (32 new tests)

## Phase 5 — Agents & Orchestration ✅ (34/34 Phase 5 tests pass; full agent pipeline verified)
- [x] 5.1 Agent framework: base class + orchestrator loop (LLM decides → tools → backend validation → LLM final answer); structured data passed between agents
- [x] 5.2 `agents/master_agent.py`: intent understanding, constraint parsing, delegation, result combination, replanning triggers
- [x] 5.3 `agents/planner_agent.py`: end-to-end plan generation pipeline (constraints → transport → stays → places → weather → route → budget → daily itinerary → risks → contingencies)
- [x] 5.4 `agents/transport_agent.py`, `accommodation_agent.py`, `places_agent.py` (compare options; never invent prices/times)
- [x] 5.5 `agents/route_agent.py` + `budget_agent.py`: wrap Phase 4 services with LLM reasoning on top
- [x] 5.6 `agents/weather_risk_agent.py`: influences itinerary decisions — rain → reschedule/indoor swaps, heat → morning/evening split, severe weather → alternate day/location; clearly separates live data / forecast / inference / recommendation
- [x] 5.7 `agents/contingency_agent.py` (structured decision tree generator)
- [x] 5.8 Mode A API: `POST /trips/{id}/generate` — full AI auto-plan, editable afterwards
- [x] 5.9 Recommendation model + `GET /trips/{id}/recommendations`: name, cost, distance, duration, rating, weather suitability, category, reason, data source, confidence, one-click "Add to Day N"
- [x] 5.10 Integration tests: orchestration flows with mocked LLM + tools (34 tests)

## Phase 6 — Agentic Features: Copilot, Contingency, What-If ✅ (25/25 Phase 6 tests pass; 154/154 total backend tests pass)
- [x] 6.1 `POST /trips/{id}/copilot` + `copilot_messages` persistence; Copilot uses trip state + tools (handles "what after Baga?", "reduce cost ₹5,000", "indoor tonight", "is this realistic?", etc.)
- [x] 6.2 AI Copilot chat panel in frontend, context-aware to current trip
- [x] 6.3 Suggestion protocol: every AI change = structured proposal {problem, change, reason, impact} with Accept / Reject / Edit buttons — AI never silently mutates itinerary
- [x] 6.4 On accept: backend validates → update itinerary → recalc budget → recalc routes → recheck weather/conflicts (full cascade)
- [x] 6.5 Contingency Builder: structured decision-tree/graph (Plan A + B/C/D for weather / transport / accommodation), each node with trigger, condition, affected activities, fallback plan, budget & time impact, confidence, reason, approval requirement; stored in `contingencies`; explainable
- [x] 6.6 ContingencyTree visualization component
- [x] 6.7 Dynamic re-planning: detect changed conditions on re-check → propose re-plan via suggestion protocol
- [x] 6.8 What-if simulation `POST /trips/{id}/simulate`: flight delay / rain / budget change / fewer travelers / hotel unavailable / extra day — runs the same itinerary + tool infrastructure, shows impact chain + budget delta + contingency
- [x] 6.9 E2E tests for the two spec scenarios (generate→edit→weather→accept→recalc; custom itinerary→conflict→suggestion→accept)

## Phase 7 — Mode C polish, Group Travel, UX
- [ ] 7.1 AI Assisted Builder: live conflict/feasibility detection as user edits, with reschedule suggestion cards
- [ ] 7.2 Trip dashboard tabs: Overview / Itinerary / Builder / Copilot / Map / Budget / Weather / Recommendations / Risks / Contingencies
- [ ] 7.3 WeatherPanel with per-day forecast + per-activity weather risk
- [ ] 7.4 Group travel: per-traveler preferences, overlap/conflict analysis, balanced-plan weighting (e.g., Beach 90% / Food 85% …) feeding Planner Agent
- [ ] 7.5 Source-transparency UI badges ("Weather API · updated 10 min ago")
- [ ] 7.6 Observability: request IDs, agent selected, tool called, tool latency, failures, LLM latency, approval/rejection events (no secrets logged)

## Phase 8 — Hardening, Testing, Demo, Deploy
- [ ] 8.1 Full error handling pass: API timeout, rate limit, invalid creds, missing/partial data, LLM failure, MCP failure, network failure — app never crashes
- [ ] 8.2 Rate limiting + input validation audit; security checklist (env-only secrets, backend-only 3rd-party calls, authz on every route)
- [ ] 8.3 Test suite complete: unit (budget/time/conflict/route/weather/contingency) + integration (MCP, endpoints, DB, Redis) + E2E
- [ ] 8.4 Demo mode with labeled mock data; scripted demo scenario (Bengaluru→Goa, 4 pax, 5 days, ₹50,000) covering all 10 steps of spec §32
- [ ] 8.5 Optional stretch: voice input (speech→intent), destination-image multimodal ("where could this be?")
- [ ] 8.6 Deployment (Docker; one-command `docker compose up` demo)
- [ ] 8.7 Docs: README with setup, architecture diagram, demo script

---

## Task Workflow (how to use this file)
1. Pick the topmost unchecked task in the lowest incomplete phase.
2. Mark it `[~]` before starting, `[x]` when done (with a one-line note if useful).
3. Never skip the tests subtasks — they gate phase completion.
4. Architecture checkpoints (enforced in review):
   - No arithmetic / travel-time / price invention in LLM code paths
   - Every external call goes through MCP/tool interfaces
   - Every AI itinerary change goes through the suggestion/approval protocol
   - All providers (LLM, flights, maps, weather) swappable via config
