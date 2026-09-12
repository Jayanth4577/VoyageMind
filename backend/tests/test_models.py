"""Model-level checks: relationships, JSON fields, cascade behavior."""

from datetime import date

from app.core.database import SessionLocal
from app.models import (
    Activity,
    BudgetItem,
    Contingency,
    ItineraryDay,
    Trip,
    User,
)


def make_user_with_trip(db) -> tuple[User, Trip]:
    user = User(email="model-test@example.com", hashed_password="x", display_name="T")
    db.add(user)
    db.flush()
    trip = Trip(
        owner_id=user.id,
        destination_name="Goa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
        currency="INR",
        preferences={"interests": ["beaches"]},
    )
    db.add(trip)
    db.flush()
    day = ItineraryDay(trip_id=trip.id, day_number=1, date=date(2026, 10, 1))
    db.add(day)
    db.flush()
    activity = Activity(
        trip_id=trip.id,
        day_id=day.id,
        name="Baga Beach",
        category="BEACH",
        start_time="10:00",
        end_time="12:00",
        estimated_cost=0,
        weather_sensitive=True,
        source="user",
        meta={"external_place_id": "osm:123"},
    )
    db.add(activity)
    db.add(BudgetItem(trip_id=trip.id, category="accommodation", label="Hotel", amount=12000))
    db.add(
        Contingency(
            trip_id=trip.id,
            plan_level="B",
            trigger="RAIN",
            condition="rain_probability > 0.6",
            affected_activity_ids=[activity.id],
            fallback_plan=["museum", "cafe"],
            budget_impact=800,
            requires_user_approval=True,
        )
    )
    db.commit()
    return user, trip


def test_activity_and_relations_roundtrip(db_tables):
    db = SessionLocal()
    try:
        user, trip = make_user_with_trip(db)
        loaded_trip = db.get(Trip, trip.id)
        assert loaded_trip.owner_id == user.id
        assert loaded_trip.days[0].activities[0].name == "Baga Beach"
        assert loaded_trip.days[0].activities[0].meta["external_place_id"] == "osm:123"

        items = {i.category: i.amount for i in loaded_trip.budget_items}
        assert items == {"accommodation": 12000}

        cont = db.query(Contingency).filter_by(trip_id=trip.id).one()
        assert cont.trigger == "RAIN"
        assert cont.requires_user_approval is True
    finally:
        db.close()


def test_trip_cascade_deletes_days_and_activities(db_tables):
    db = SessionLocal()
    try:
        user, trip = make_user_with_trip(db)
        db.delete(db.get(Trip, trip.id))
        db.commit()
        assert db.query(Activity).filter_by(trip_id=trip.id).count() == 0
        assert db.query(ItineraryDay).filter_by(trip_id=trip.id).count() == 0
        assert db.get(User, user.id) is not None
    finally:
        db.close()
