"""RouteService — day route evaluation & optimization reports (spec §8).

Travel times come from real routing data (Maps MCP / OSRM). The optimization is
a report + suggested order; the USER applies it via the reorder endpoint —
the service never silently reorders the itinerary (spec §16).
"""
from sqlalchemy.orm import Session

from app.mcp.travel_mcp import travel_mcp
from app.models import ItineraryDay, Trip


def _located(day: ItineraryDay):
    return [a for a in day.activities if a.latitude is not None and a.longitude is not None]


async def day_route_report(db: Session, trip: Trip, day: ItineraryDay) -> dict:
    acts = _located(day)
    base = {
        "day_id": day.id,
        "day_number": day.day_number,
        "total_activities": len(day.activities),
        "routed_activities": len(acts),
    }
    if len(acts) < 2:
        return {
            **base,
            "status": "not_enough_locations",
            "message": "At least 2 located activities are needed to evaluate a route",
        }

    points = [
        {"latitude": a.latitude, "longitude": a.longitude, "activity_id": a.id}
        for a in acts
    ]
    current = await travel_mcp.maps.calculate_route(points)
    optimized = await travel_mcp.maps.optimize_route(points)

    current_order_ids = [a.id for a in acts]
    order = optimized.get("order") or list(range(len(points)))
    suggested_ids = [
        points[i]["activity_id"] for i in order if isinstance(i, int) and 0 <= i < len(points)
    ]

    current_dur = current.get("duration_minutes")
    optimized_dur = optimized.get("duration_minutes")
    saved = max(0, (current_dur or 0) - (optimized_dur or 0))

    return {
        **base,
        "status": "ok",
        "current_duration_minutes": current_dur,
        "current_distance_km": current.get("distance_km"),
        "optimized_duration_minutes": optimized_dur,
        "saved_minutes": saved,
        "current_order_ids": current_order_ids,
        "suggested_order_ids": suggested_ids,
        "already_optimal": suggested_ids == current_order_ids,
        "source": optimized.get("source"),
        "is_mock": bool(optimized.get("is_mock")) or bool(current.get("is_mock")),
        "note": optimized.get("note", ""),
    }


async def itinerary_route_report(db: Session, trip: Trip) -> dict:
    reports = []
    for day in sorted(trip.days, key=lambda d: d.day_number):
        reports.append(await day_route_report(db, trip, day))
    total_saved = sum(
        r.get("saved_minutes", 0) for r in reports if r.get("status") == "ok"
    )
    optimizable = [r for r in reports if r.get("status") == "ok"]
    return {
        "trip_id": trip.id,
        "days": reports,
        "total_saved_minutes": total_saved,
        "days_evaluated": len(optimizable),
        "already_optimal": all(r.get("already_optimal") for r in optimizable),
    }
