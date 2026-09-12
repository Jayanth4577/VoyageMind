"""WeatherService tests — deterministic thresholds (spec §5)."""
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.core.database import SessionLocal
from app.mcp import travel_mcp as tm
from app.models import Activity, ItineraryDay, Trip, User
from app.services import weather_service


def day_forecast(
    d, rain_prob=0, precip=0.0, temp_max=28.0, significant=False
):
    return {
        "date": d,
        "rain_probability": rain_prob,
        "precipitation_mm": precip,
        "temp_max_c": temp_max,
        "significant_rain": significant,
    }


def seed(db, activity_specs):
    user = User(email=f"wx-{id(db)}@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    trip = Trip(
        owner_id=user.id,
        destination_name="Goa",
        destination_lat=15.3,
        destination_lng=74.1,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
    )
    db.add(trip)
    db.flush()
    day1 = ItineraryDay(trip_id=trip.id, day_number=1, date=date(2026, 10, 1))
    day2 = ItineraryDay(trip_id=trip.id, day_number=2, date=date(2026, 10, 2))
    db.add_all([day1, day2])
    db.flush()
    for day, specs in ((day1, activity_specs[0]), (day2, activity_specs[1])):
        for i, spec in enumerate(specs):
            db.add(
                Activity(
                    trip_id=trip.id,
                    day_id=day.id,
                    name=spec.get("name", f"Act{i}"),
                    category=spec.get("category", "BEACH"),
                    position=i,
                    weather_sensitive=spec.get("weather_sensitive", True),
                    indoor=spec.get("indoor", False),
                )
            )
    db.commit()
    return trip


def patch_forecast(monkeypatch, daily, alerts=None):
    payload = {"source": "open-meteo", "is_mock": False, "daily": daily}
    payload["alerts"] = alerts or []
    monkeypatch.setattr(
        tm.travel_mcp.weather, "get_weather", AsyncMock(return_value=payload)
    )


@pytest.mark.anyio
async def test_rain_day_flags_outdoor_activities(db_tables, monkeypatch):
    db = SessionLocal()
    try:
        trip = seed(
            db,
            [
                [
                    {"name": "Museum", "indoor": True},
                    {"name": "Cafe", "category": "CAFE", "indoor": True},
                ],
                [
                    {"name": "Baga Beach"},
                    {"name": "Walk", "category": "ACTIVITY", "weather_sensitive": False},
                ],
            ],
        )
        patch_forecast(
            monkeypatch,
            [
                day_forecast("2026-10-01"),
                day_forecast("2026-10-02", rain_prob=85, precip=12, significant=True),
            ],
        )
        report = await weather_service.check_weather_conflicts(db, trip)
        assert report["status"] == "ok"
        assert report["days_at_risk"] == 1
        day2 = next(d for d in report["days"] if d["day_number"] == 2)
        assert day2["risk"] == "rain"
        # only the weather-sensitive outdoor activity is affected
        assert len(day2["affected_activity_ids"]) == 1
        assert "rain" in day2["suggestion"]
        day1 = next(d for d in report["days"] if d["day_number"] == 1)
        assert day1["risk"] == "none"
    finally:
        db.close()


@pytest.mark.anyio
async def test_heat_day(db_tables, monkeypatch):
    db = SessionLocal()
    try:
        trip = seed(db, [[{"name": "Fort walk"}], []])
        patch_forecast(monkeypatch, [day_forecast("2026-10-01", temp_max=41)])
        report = await weather_service.check_weather_conflicts(db, trip)
        day1 = report["days"][0]
        assert day1["risk"] == "heat"
        assert "midday indoors" in day1["suggestion"]
    finally:
        db.close()


@pytest.mark.anyio
async def test_demo_dates_fall_back_to_positional_match(db_tables, monkeypatch):
    db = SessionLocal()
    try:
        trip = seed(db, [[{"name": "Beach"}], [{"name": "Museum", "indoor": True}]])
        patch_forecast(
            monkeypatch,
            [
                day_forecast("demo-day-1", rain_prob=95, precip=20, temp_max=26),
                day_forecast("demo-day-2"),
            ],
        )
        report = await weather_service.check_weather_conflicts(db, trip)
        day1 = next(d for d in report["days"] if d["day_number"] == 1)
        assert day1["risk"] == "rain"  # positional match despite synthetic dates
        day2 = next(d for d in report["days"] if d["day_number"] == 2)
        assert day2["risk"] == "none"
    finally:
        db.close()


@pytest.mark.anyio
async def test_severe_alerts_override(db_tables, monkeypatch):
    db = SessionLocal()
    try:
        trip = seed(db, [[{"name": "Beach"}], []])
        patch_forecast(
            monkeypatch,
            [day_forecast("2026-10-01")],
            alerts=[{"event": "cyclone"}],
        )
        report = await weather_service.check_weather_conflicts(db, trip)
        assert report["days"][0]["risk"] == "severe"
    finally:
        db.close()


@pytest.mark.anyio
async def test_unresolved_location(db_tables, monkeypatch):
    db = SessionLocal()
    try:
        trip = seed(db, [[], []])
        trip.destination_lat = None
        trip.destination_lng = None
        db.commit()
        monkeypatch.setattr(
            tm.travel_mcp.maps,
            "geocode_place",
            AsyncMock(return_value={"source": "test", "results": []}),
        )
        report = await weather_service.check_weather_conflicts(db, trip)
        assert report["status"] == "unresolved_location"
        assert report["days"] == []
    finally:
        db.close()
