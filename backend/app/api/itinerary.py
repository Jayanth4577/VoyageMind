"""Itinerary + activity endpoints (spec §24)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.models import Activity, ItineraryDay, Trip
from app.schemas.activity_schema import ActivityCreate, ActivityOut, ActivityUpdate
from app.schemas.itinerary_schema import ItineraryDayOut, ItineraryOut
from app.services import itinerary_service
from app.services.trip_service import get_owned_trip

router = APIRouter(tags=["itinerary"])


def _load(db, trip_id: str, user) -> Trip:
    return get_owned_trip(db, trip_id, user)


@router.get("/trips/{trip_id}/itinerary", response_model=ItineraryOut)
def get_itinerary(trip_id: str, user: CurrentUser, db: DbSession) -> ItineraryOut:
    trip = _load(db, trip_id, user)
    days = sorted(trip.days, key=lambda d: d.day_number)
    return ItineraryOut(trip_id=trip.id, days=days)


@router.post(
    "/trips/{trip_id}/activities",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
)
def add_activity(trip_id: str, body: ActivityCreate, user: CurrentUser, db: DbSession) -> Activity:
    trip = _load(db, trip_id, user)
    return itinerary_service.add_activity(db, trip, body)


@router.put("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: str, body: ActivityUpdate, user: CurrentUser, db: DbSession
) -> Activity:
    trip = _find_trip_by_activity(db, activity_id, user)
    return itinerary_service.update_activity(db, trip, activity_id, body)


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: str, user: CurrentUser, db: DbSession) -> None:
    trip = _find_trip_by_activity(db, activity_id, user)
    itinerary_service.delete_activity(db, trip, activity_id)


class MoveIn(BaseModel):
    target_day_id: str
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


@router.post("/activities/{activity_id}/move", response_model=ActivityOut)
def move_activity(activity_id: str, body: MoveIn, user: CurrentUser, db: DbSession) -> Activity:
    trip = _find_trip_by_activity(db, activity_id, user)
    return itinerary_service.move_activity(
        db, trip, activity_id, body.target_day_id, body.start_time, body.end_time
    )


class ReorderIn(BaseModel):
    activity_ids: list[str]


@router.post("/trips/{trip_id}/days/{day_id}/reorder", response_model=ItineraryDayOut)
def reorder_day(
    trip_id: str, day_id: str, body: ReorderIn, user: CurrentUser, db: DbSession
) -> ItineraryDay:
    trip = _load(db, trip_id, user)
    return itinerary_service.reorder_day(db, trip, day_id, body.activity_ids)


class ConflictReport(BaseModel):
    trip_id: str
    issues: list[dict]
    has_conflicts: bool
    has_warnings: bool


@router.post("/trips/{trip_id}/check-conflicts", response_model=ConflictReport)
def check_conflicts(trip_id: str, user: CurrentUser, db: DbSession) -> ConflictReport:
    trip = _load(db, trip_id, user)
    issues = itinerary_service.validate_itinerary(db, trip)
    return ConflictReport(
        trip_id=trip.id,
        issues=issues,
        has_conflicts=any(i["severity"] == "conflict" for i in issues),
        has_warnings=any(i["severity"] == "warning" for i in issues),
    )


def _find_trip_by_activity(db, activity_id: str, user) -> Trip:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return get_owned_trip(db, activity.trip_id, user)
