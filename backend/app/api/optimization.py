"""Optimization endpoints (spec §24): route, budget, weather conflict checks.

These endpoints return reports + suggested changes; applying changes stays
with the user (reorder/accept flows) per the user-control principle.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.services import itinerary_service, optimization_service, weather_service
from app.services.trip_service import get_owned_trip

router = APIRouter(prefix="/trips", tags=["optimization"])


class OptimizeRouteIn(BaseModel):
    day_id: str | None = None


@router.post("/{trip_id}/optimize-route")
async def optimize_route(
    trip_id: str,
    user: CurrentUser,
    db: DbSession,
    body: OptimizeRouteIn | None = None,
) -> dict:
    trip = get_owned_trip(db, trip_id, user)
    if body is not None and body.day_id:
        day = itinerary_service.get_day(db, trip, body.day_id)
        return await optimization_service.optimize_day(db, trip, day)
    return await optimization_service.optimize_itinerary(db, trip)


@router.post("/{trip_id}/optimize-budget")
def optimize_budget(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    trip = get_owned_trip(db, trip_id, user)
    return optimization_service.budget_savings_plan(db, trip)


@router.post("/{trip_id}/check-weather")
async def check_weather(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    trip = get_owned_trip(db, trip_id, user)
    return await weather_service.check_weather_conflicts(db, trip)
