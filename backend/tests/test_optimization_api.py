"""Optimization endpoint tests: ownership, route reports, budget plan, weather check."""
import uuid
from unittest.mock import AsyncMock

from app.core.database import SessionLocal
from app.mcp import travel_mcp as tm
from app.models import Activity, BudgetItem


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers, **extra):
    payload = {
        "destination_name": "Goa",
        "start_date": "2026-10-01",
        "end_date": "2026-10-02",
        "total_budget": 20000,
        "currency": "INR",
    }
    payload.update(extra)
    return client.post("/trips", json=payload, headers=headers).json()


def seed_activity(trip_id, day_id, name, lat, lng):
    db = SessionLocal()
    try:
        act = Activity(
            trip_id=trip_id, day_id=day_id, name=name, position=0,
            latitude=lat, longitude=lng,
        )
        db.add(act)
        db.commit()
        return act.id
    finally:
        db.close()


def test_optimize_route_endpoint(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    seed_activity(trip["id"], trip["days"][0]["id"], "A", 15.5, 73.75)
    seed_activity(trip["id"], trip["days"][0]["id"], "B", 15.29, 73.96)

    monkeypatch.setattr(
        tm.travel_mcp.maps, "calculate_route",
        AsyncMock(
            return_value={"source": "osrm", "is_mock": False, "duration_minutes": 120}
        ),
    )
    monkeypatch.setattr(
        tm.travel_mcp.maps, "optimize_route",
        AsyncMock(
            return_value={
                "source": "osrm",
                "is_mock": False,
                "order": [1, 0],
                "duration_minutes": 80,
            }
        ),
    )

    res = client.post(f"/trips/{trip['id']}/optimize-route", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total_saved_minutes"] == 40
    assert body["route"]["days"][0]["status"] == "ok"

    # single-day variant
    day_id = trip["days"][0]["id"]
    res2 = client.post(
        f"/trips/{trip['id']}/optimize-route", json={"day_id": day_id}, headers=headers
    )
    assert res2.status_code == 200
    assert len(res2.json()["days"]) == 1


def test_optimize_budget_endpoint(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    db = SessionLocal()
    try:
        db.add(BudgetItem(trip_id=trip["id"], category="accommodation", label="A", amount=15000))
        db.add(BudgetItem(trip_id=trip["id"], category="accommodation", label="B", amount=9000))
        db.commit()
    finally:
        db.close()

    res = client.post(f"/trips/{trip['id']}/optimize-budget", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "over_budget"
    assert body["over_budget_amount"] == 4000
    assert body["candidates"][0]["label"] == "A"
    assert body["candidates"][0]["potential_saving"] == 6000.0  # median of others [9000]


def test_check_weather_endpoint(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers, destination_lat=15.3, destination_lng=74.1)
    monkeypatch.setattr(
        tm.travel_mcp.weather,
        "get_weather",
        AsyncMock(
            return_value={
                "source": "open-meteo",
                "is_mock": False,
                "daily": [
                    {
                        "date": "2026-10-01",
                        "rain_probability": 90,
                        "precipitation_mm": 15,
                        "temp_max_c": 26,
                    }
                ],
                "alerts": [],
            }
        ),
    )
    res = client.post(f"/trips/{trip['id']}/check-weather", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["days"][0]["risk"] == "rain"


def test_optimization_requires_ownership(client):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    trip = make_trip(client, headers_a)
    for path in ("optimize-route", "optimize-budget", "check-weather"):
        res = client.post(f"/trips/{trip['id']}/{path}", headers=headers_b)
        assert res.status_code == 404, path
