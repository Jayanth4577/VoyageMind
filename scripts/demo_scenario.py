"""VoyageMind demo scenario — spec §32, end to end over the real API.

Bengaluru -> Goa · 4 travelers · 5 days · Rs 50,000.

Prerequisites:
    1. Travel MCP Gateway (demo mode needs no external API keys):
       TRAVEL_MCP_DEMO_MODE=1 uvicorn travel_mcp.server:app --port 8001
       (from travel-mcp-server/, with its venv active)
    2. Backend pointing at the gateway:
       TRAVEL_MCP_URL=http://localhost:8001 uvicorn app.main:app --port 8000
       (from backend/, with its venv active)
    3. Optional: an LLM key in backend/.env for the Mode A / Copilot steps.

Run:  python scripts/demo_scenario.py            (backend on :8000)
      python scripts/demo_scenario.py --base-url http://localhost:9000
"""

import argparse
import asyncio
import os
import sys

import httpx

STEP = "\n\033[1;36m== {} ==\033[0m"


def note(msg: str) -> None:
    print(f"\033[33m{msg}\033[0m")


def money(x):
    return f"Rs {x:,.0f}"


async def main(base_url: str) -> int:
    print("VoyageMind demo scenario: Bengaluru -> Goa, 4 travelers, 5 days, Rs 50,000")
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as c:
        # -- Setup: demo user + trip -----------------------------------------
        email = "demo@voyagemind.app"
        r = await c.post(
            "/auth/register",
            json={"email": email, "password": "demopass123", "display_name": "Demo"},
        )
        if r.status_code == 409:
            r = await c.post(
                "/auth/login", json={"email": email, "password": "demopass123"}
            )
        r.raise_for_status()
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        print(STEP.format("Step 1: trip inputs"))
        trip = (
            await c.post(
                "/trips",
                headers=headers,
                json={
                    "origin_name": "Bengaluru",
                    "destination_name": "Goa",
                    "start_date": "2026-11-01",
                    "end_date": "2026-11-05",
                    "num_travelers": 4,
                    "total_budget": 50000,
                    "currency": "INR",
                    "trip_style": "relaxed",
                    "preferences": {"interests": ["beaches", "local food", "nightlife", "culture"]},
                },
            )
        ).json()
        tid = trip["id"]
        days = {d["day_number"]: d for d in trip["days"]}
        print(f"  trip {tid} created: {trip['origin_name']} -> {trip['destination_name']}")

        print(STEP.format("Step 2: AI generates an initial itinerary (Mode A)"))
        gen = await c.post(f"/trips/{tid}/generate", headers=headers)
        if gen.status_code == 200:
            body = gen.json()
            print(f"  plan status: {body['status']}; reasoning: {(body.get('reasoning') or '')[:120]}")
        else:
            note(
                "  skipped — no LLM provider configured (set GEMINI_API_KEY in "
                "backend/.env). The demo continues with the manual builder."
            )

        print(STEP.format("Steps 3-4: switch to Custom Builder; user moves activities"))
        day1, day2 = days[1]["id"], days[2]["id"]
        activities = [
            ("Baga Beach", "BEACH", day2, "10:00", 120, 0, 15.555, 73.751),
            ("Aguada Fort", "MUSEUM", day2, "10:30", 90, 0, 15.505, 73.773),
            ("Panaji heritage walk", "ACTIVITY", day2, "11:00", 120, 300, 15.490, 73.827),
            ("Beachside seafood dinner", "RESTAURANT", day2, "19:30", 90, 2400, 15.555, 73.751),
            ("Kayaking at Candolim", "ACTIVITY", day2, "16:00", 120, 1500, 15.515, 73.770),
        ]
        for name, cat, day_id, start, mins, cost, lat, lng in activities:
            r = await c.post(
                f"/trips/{tid}/activities",
                headers=headers,
                json={
                    "day_id": day_id,
                    "name": name,
                    "category": cat,
                    "start_time": start,
                    "duration_minutes": mins,
                    "estimated_cost": cost,
                    "weather_sensitive": cat in ("BEACH", "ACTIVITY"),
                    "latitude": lat,
                    "longitude": lng,
                },
            )
            r.raise_for_status()
        print(f"  {len(activities)} structured activities added (overlapping times on purpose)")

        print(STEP.format("Step 5: Route Agent detects increased travel time"))
        route = (await c.post(f"/trips/{tid}/optimize-route", headers=headers)).json()
        for d in route["route"]["days"]:
            if d.get("status") == "ok":
                print(
                    f"  Day {d['day_number']}: {d['current_duration_minutes']} min -> "
                    f"optimized {d['optimized_duration_minutes']} min "
                    f"(saved {d['saved_minutes']} min, source {d['source']})"
                )

        print(STEP.format("Step 6: Budget Agent recalculates cost"))
        budget = (await c.get(f"/trips/{tid}/budget", headers=headers)).json()
        print(f"  spent {money(budget['spent'])} of {money(budget['total_budget'] or 0)} ({budget['state']})")
        over = (await c.post(f"/trips/{tid}/optimize-budget", headers=headers)).json()
        if over.get("status") == "over_budget":
            for cand in over["candidates"]:
                print(f"  saving candidate: {cand['label']} -> {money(cand['target_amount'])}")

        print(STEP.format("Step 7: Weather Agent checks the forecast"))
        wx = (await c.get(f"/trips/{tid}/weather", headers=headers)).json()
        src = "DEMO DATA" if wx.get("is_mock") else wx.get("source")
        print(f"  forecast source: {src}")
        for day in wx.get("daily", [])[:5]:
            print(
                f"  {day.get('date', '?')}: max {day.get('temp_max_c')}C, "
                f"rain {day.get('rain_probability')}%"
            )

        print(STEP.format("Step 8: conflicts + AI suggestion (Accept / Reject)"))
        report = (await c.post(f"/trips/{tid}/check-conflicts", headers=headers)).json()
        for issue in report["issues"][:4]:
            print(f"  {'X' if issue['severity'] == 'conflict' else '!'} Day {issue['day_number']}: {issue['message']}")
        copilot = await c.post(
            f"/trips/{tid}/copilot",
            headers=headers,
            json={"message": "Schedule conflicts were detected on Day 2. Propose a realistic reschedule."},
        )
        if copilot.status_code == 200:
            body = copilot.json()
            sugg = body.get("suggestions")
            if sugg:
                s = sugg[0]
                print(f"  AI proposes: {s.get('problem')}")
                sid = s["suggestion_id"]
                accept = await c.post(
                    f"/trips/{tid}/suggestions/{sid}/action",
                    headers=headers,
                    json={"action": "accept"},
                )
                if accept.status_code == 200:
                    cascade = accept.json().get("cascade", {}).get("budget", {})
                    print(f"  accepted -> cascade recalculated budget: {cascade}")
            elif copilot.json()["message"]["data"].get("error"):
                note("  AI step skipped — no LLM provider configured")
        else:
            note("  AI step skipped — no LLM provider configured")

        print(STEP.format("Step 9: Contingency Builder (Plan A/B/C/D)"))
        whatif = await c.post(
            f"/trips/{tid}/simulate",
            headers=headers,
            json={"scenario": "flight_delay", "parameters": {"delay_hours": 3}},
        )
        if whatif.status_code == 200:
            result = whatif.json()
            for link in result.get("impact_chain", []):
                print(f"  {link}")
        conts = (await c.get(f"/trips/{tid}/contingencies", headers=headers)).json()
        print(f"  {len(conts)} contingency plan(s) stored")

        print(STEP.format("Step 10: What-if — flight delayed by 3 hours (shown above)"))
        itinerary = (await c.get(f"/trips/{tid}/itinerary", headers=headers)).json()
        total = sum(
            a["estimated_cost"] for d in itinerary["days"] for a in d["activities"]
        )
        print(f"  final itinerary: {sum(len(d['activities']) for d in itinerary['days'])} activities")
        print(f"  activity costs total: {money(total)}")

        print("\nDemo complete — open the frontend (http://localhost:3000) to explore this trip.")
        note(f"  login: {email} / demopass123")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VoyageMind demo scenario")
    parser.add_argument("--base-url", default=os.environ.get("DEMO_BASE_URL", "http://localhost:8000"))
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.base_url)))
