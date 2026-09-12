"""RouteService tests — ordering reports with real-coordinate fake routing data."""
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.core.database import SessionLocal
from app.mcp import travel_mcp as tm
from app.models import Activity, ItineraryDay, Trip, User
from app.services import route_service


@pytest.fixture()
def scenario(db_tables):
    db = SessionLocal()
    try:
        user = User(email=f"route-{id(db)}@example.com", hashed_password="x")
        db.add(user)
        db.flush()
        trip = Trip(
            owner_id=user.id,
            destination_name="Goa",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )
        db.add(trip)
        db.flush()
        day = ItineraryDay(trip_id=trip.id, day_number=1, date=date(2026, 10, 1))
        db.add(day)
        db.flush()
        acts = []
        for i, (lat, lng) in enumerate([(15.5, 73.75), (15.29, 73.96), (15.45, 73.8)]):
            act = Activity(
                trip_id=trip.id,
                day_id=day.id,
                name=f"Stop{i}",
                position=i,
                start_time="10:00",
                latitude=lat,
                longitude=lng,
            )
            db.add(act)
            acts.append(act)
        db.commit()
        yield db, trip, day, acts
    finally:
        db.close()


def patch_maps(monkeypatch, current, optimized):
    monkeypatch.setattr(tm.travel_mcp.maps, "calculate_route", AsyncMock(return_value=current))
    monkeypatch.setattr(tm.travel_mcp.maps, "optimize_route", AsyncMock(return_value=optimized))


@pytest.mark.anyio
async def test_day_route_report_saves_time(scenario, monkeypatch):
    db, trip, day, acts = scenario
    # Current order 0->1->2 takes 120 min; optimized order [0,2,1] takes 75 min
    patch_maps(
        monkeypatch,
        current={"source": "osrm", "is_mock": False, "duration_minutes": 120},
        optimized={
            "source": "osrm",
            "is_mock": False,
            "order": [0, 2, 1],
            "duration_minutes": 75,
        },
    )
    report = await route_service.day_route_report(db, trip, day)
    assert report["status"] == "ok"
    assert report["current_duration_minutes"] == 120
    assert report["optimized_duration_minutes"] == 75
    assert report["saved_minutes"] == 45
    assert report["suggested_order_ids"] == [acts[0].id, acts[2].id, acts[1].id]
    assert report["already_optimal"] is False
    assert report["is_mock"] is False


@pytest.mark.anyio
async def test_day_route_report_already_optimal(scenario, monkeypatch):
    db, trip, day, acts = scenario
    patch_maps(
        monkeypatch,
        current={"source": "osrm", "is_mock": False, "duration_minutes": 60},
        optimized={"source": "osrm", "is_mock": False, "order": [0, 1, 2], "duration_minutes": 60},
    )
    report = await route_service.day_route_report(db, trip, day)
    assert report["already_optimal"] is True
    assert report["saved_minutes"] == 0


@pytest.mark.anyio
async def test_day_with_few_located_activities(scenario):
    db, trip, day, acts = scenario
    # strip coordinates from all but one
    for act in acts[1:]:
        act.latitude = None
        act.longitude = None
    db.commit()
    report = await route_service.day_route_report(db, trip, day)
    assert report["status"] == "not_enough_locations"


@pytest.mark.anyio
async def test_itinerary_report_aggregates_savings(scenario, monkeypatch):
    db, trip, day, acts = scenario
    patch_maps(
        monkeypatch,
        current={"source": "osrm", "is_mock": False, "duration_minutes": 120},
        optimized={
            "source": "osrm",
            "is_mock": False,
            "order": [0, 2, 1],
            "duration_minutes": 75,
        },
    )
    report = await route_service.itinerary_route_report(db, trip)
    assert report["days_evaluated"] == 1
    assert report["total_saved_minutes"] == 45
    assert report["already_optimal"] is False


@pytest.mark.anyio
async def test_heuristic_fallback_labels_itself(scenario, monkeypatch):
    db, trip, day, acts = scenario

    class FailingClient:
        async def call_tool(self, name, arguments=None):
            return {"status": "error", "error": "osrm down"}

    # Swap the facade's underlying client so optimize_route runs its own fallback
    monkeypatch.setattr(tm.travel_mcp.maps, "_client", FailingClient())
    report = await route_service.day_route_report(db, trip, day)
    assert report["source"] == "heuristic-nearest-neighbor"
    assert report["is_mock"] is True
    assert "HEURISTIC" in report["note"]
    # nearest-neighbor from stop0 must visit stop1 (15.29,73.96) or stop2 (15.45,73.8) by distance
    assert report["suggested_order_ids"][0] == acts[0].id
