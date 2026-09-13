# Demo scenario — Bengaluru → Goa (spec §32)

The full 10-step demo runs against the real API with **zero external API keys**
in demo mode (all live data is clearly labeled `DEMO DATA`).

## One-time setup

```bash
# 1. Travel MCP Gateway in demo mode (no keys needed)
cd travel-mcp-server
pip install -e ".[dev]"
TRAVEL_MCP_DEMO_MODE=1 uvicorn travel_mcp.server:app --port 8001   # Windows: set TRAVEL_MCP_DEMO_MODE=1 && uvicorn ...

# 2. Backend, pointed at the gateway
cd ../backend
pip install -e ".[dev]"
set TRAVEL_MCP_URL=http://localhost:8001    # Windows
uvicorn app.main:app --port 8000
```

Optional: set `GEMINI_API_KEY` in `backend/.env` to enable the Mode A /
Copilot steps — the script skips them gracefully otherwise.

## Run it

```bash
python scripts/demo_scenario.py
```

The script walks the spec's exact 10 steps:

| # | Spec step | Where it happens |
|---|---|---|
| 1 | Enter trip (BLR→Goa, 4 pax, 5 days, ₹50,000) | `POST /trips` |
| 2 | AI generates an initial itinerary | `POST /trips/{id}/generate` (needs LLM key) |
| 3–4 | User switches to Custom Builder, moves activities | `POST /trips/{id}/activities` (overlapping times, deliberately) |
| 5 | Route Agent detects increased travel time | `POST /trips/{id}/optimize-route` → before/after minutes |
| 6 | Budget Agent recalculates cost | `GET /budget` + `POST /optimize-budget` → savings candidates |
| 7 | Weather Agent checks the forecast | `GET /trips/{id}/weather` (source-labeled) |
| 8 | AI suggests Beach→Museum / kayaking→Day 3 | `POST /check-conflicts` + Copilot suggestion → Accept |
| 9 | Contingency Builder generates Plan A/B/C/D | `POST /simulate` + `GET /contingencies` |
| 10 | "What if my flight is delayed by 3 hours?" | `POST /simulate {flight_delay, delay_hours: 3}` impact chain |

Then open the frontend (`http://localhost:3000`, login `demo@voyagemind.app` /
`demopass123`) and explore the same trip in the UI — every tab (Itinerary,
Copilot, Budget, Weather, Risks, Contingencies, Group) is live for this trip.
