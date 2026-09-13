"""Trip CRUD with per-user ownership (spec §24)."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser, DbSession
from app.models import ItineraryDay, Trip
from app.schemas.trip_schema import TripCreate, TripListOut, TripOut, TripUpdate

router = APIRouter(prefix="/trips", tags=["trips"])


def _sync_days(db, trip: Trip) -> None:
    """Ensure one ItineraryDay row per trip date (adds missing, prunes empty extras)."""
    n_days = (trip.end_date - trip.start_date).days + 1
    existing = {d.day_number: d for d in trip.days}
    for num in range(1, n_days + 1):
        if num not in existing:
            db.add(
                ItineraryDay(
                    trip_id=trip.id,
                    day_number=num,
                    date=trip.start_date + timedelta(days=num - 1),
                )
            )
    for num, day in existing.items():
        if num > n_days and not day.activities:
            db.delete(day)


def _owned_trip(trip_id: str, user, db) -> Trip:
    trip = db.scalar(
        select(Trip)
        .options(joinedload(Trip.days))
        .where(Trip.id == trip_id, Trip.owner_id == user.id)
    )
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    return trip


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(body: TripCreate, user: CurrentUser, db: DbSession) -> Trip:
    trip = Trip(owner_id=user.id, **body.model_dump())
    db.add(trip)
    db.flush()
    _sync_days(db, trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("", response_model=TripListOut)
def list_trips(user: CurrentUser, db: DbSession) -> TripListOut:
    trips = db.scalars(select(Trip).where(Trip.owner_id == user.id)).all()
    return TripListOut(items=list(trips))


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: str, user: CurrentUser, db: DbSession) -> Trip:
    return _owned_trip(trip_id, user, db)


@router.put("/{trip_id}", response_model=TripOut)
def update_trip(trip_id: str, body: TripUpdate, user: CurrentUser, db: DbSession) -> Trip:
    trip = _owned_trip(trip_id, user, db)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(trip, field, value)
    if changes.get("start_date") or changes.get("end_date"):
        _sync_days(db, trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: str, user: CurrentUser, db: DbSession) -> None:
    trip = _owned_trip(trip_id, user, db)
    # All trip-owned children (days, activities, budget items, contingencies,
    # recommendations, events, …) cascade via relationship rules.
    db.delete(trip)
    db.commit()
