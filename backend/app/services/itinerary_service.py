"""ItineraryService — all itinerary mutations flow through here (spec §15).

The API layer calls these functions; agents must use them too (in Phase 5) so
every mutation stays validated and budget-consistent.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Activity, ItineraryDay, Trip
from app.schemas.activity_schema import ActivityCreate, ActivityUpdate
from app.services import conflict_service
from app.services.budget_service import remove_item_for_activity, upsert_item_for_activity
from app.utils.datetime_utils import add_minutes


def get_day(db: Session, trip: Trip, day_id: str) -> ItineraryDay:
    day = db.get(ItineraryDay, day_id)
    if day is None or day.trip_id != trip.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Itinerary day not found")
    return day


def get_activity(db: Session, trip: Trip, activity_id: str) -> Activity:
    activity = db.get(Activity, activity_id)
    if activity is None or activity.trip_id != trip.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return activity


def add_activity(db: Session, trip: Trip, data: ActivityCreate) -> Activity:
    day = get_day(db, trip, data.day_id)
    last_pos = db.query(Activity).filter(Activity.day_id == day.id).count()
    activity = Activity(
        trip_id=trip.id,
        day_id=day.id,
        position=last_pos,
        **data.model_dump(exclude={"day_id"}),
    )
    # Derived end_time when only start + duration are given
    if not activity.end_time and activity.start_time and activity.duration_minutes:
        activity.end_time = add_minutes(activity.start_time, activity.duration_minutes) or ""
    db.add(activity)
    db.flush()
    upsert_item_for_activity(db, activity)
    db.commit()
    db.refresh(activity)
    return activity


def update_activity(db: Session, trip: Trip, activity_id: str, data: ActivityUpdate) -> Activity:
    activity = get_activity(db, trip, activity_id)
    changes = data.model_dump(exclude_unset=True)

    if "day_id" in changes and changes["day_id"] != activity.day_id:
        target = get_day(db, trip, changes["day_id"])
        changes["position"] = db.query(Activity).filter(Activity.day_id == target.id).count()

    for field, value in changes.items():
        setattr(activity, field, value)
    if not activity.end_time and activity.start_time and activity.duration_minutes:
        activity.end_time = add_minutes(activity.start_time, activity.duration_minutes) or ""

    upsert_item_for_activity(db, activity)
    db.commit()
    db.refresh(activity)
    return activity


def move_activity(
    db: Session,
    trip: Trip,
    activity_id: str,
    target_day_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> Activity:
    """Move between days (and optionally re-time) in one validated step."""
    get_day(db, trip, target_day_id)
    payload = ActivityUpdate(day_id=target_day_id)
    if start_time is not None:
        payload.start_time = start_time
    if end_time is not None:
        payload.end_time = end_time
    return update_activity(db, trip, activity_id, payload)


def delete_activity(db: Session, trip: Trip, activity_id: str) -> None:
    activity = get_activity(db, trip, activity_id)
    remove_item_for_activity(db, activity.id)
    db.delete(activity)
    db.commit()


def reorder_day(db: Session, trip: Trip, day_id: str, activity_ids: list[str]) -> ItineraryDay:
    """Persist a manual ordering; unknown/mismatched ids are rejected wholesale."""
    day = get_day(db, trip, day_id)
    existing = {a.id for a in day.activities}
    if set(activity_ids) != existing or len(activity_ids) != len(existing):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "activity_ids must contain exactly the day's activity ids",
        )
    for pos, activity_id in enumerate(activity_ids):
        db.get(Activity, activity_id).position = pos
    db.commit()
    db.refresh(day)
    return day


def validate_itinerary(db: Session, trip: Trip) -> list[dict]:
    return conflict_service.validate_itinerary(db, trip)
