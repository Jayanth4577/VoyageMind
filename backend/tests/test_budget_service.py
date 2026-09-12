"""BudgetService unit tests — deterministic arithmetic (spec §7)."""
from datetime import date

from app.core.database import SessionLocal
from app.models import BudgetItem, Trip, User
from app.services import budget_service


def seed(db) -> Trip:
    user = User(email=f"budget-{id(db)}@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    trip = Trip(
        owner_id=user.id,
        destination_name="Goa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 3),
        currency="INR",
    )
    db.add(trip)
    db.flush()
    return trip


def add_item(db, trip, category, amount):
    item = BudgetItem(trip_id=trip.id, category=category, label=category, amount=amount)
    db.add(item)
    db.flush()
    return item


def test_summary_under_budget(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db)
        trip.total_budget = 50000
        add_item(db, trip, "transport", 12000)
        add_item(db, trip, "accommodation", 18000)
        add_item(db, trip, "food", 4500)
        db.commit()

        s = budget_service.compute_summary(db, trip)
        assert s.spent == 34500
        assert s.remaining == 15500
        assert s.state == "under"
        assert s.by_category["transport"] == 12000
    finally:
        db.close()


def test_summary_near_and_over_budget(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db)
        trip.total_budget = 10000
        add_item(db, trip, "accommodation", 9200)  # >= 90% -> near
        db.commit()
        assert budget_service.compute_summary(db, trip).state == "near"

        add_item(db, trip, "food", 2000)  # total 11200 -> over
        db.commit()
        s = budget_service.compute_summary(db, trip)
        assert s.state == "over"
        assert s.remaining == -1200
    finally:
        db.close()


def test_summary_without_budget(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db)  # total_budget stays None
        add_item(db, trip, "food", 500)
        db.commit()
        s = budget_service.compute_summary(db, trip)
        assert s.state == "unknown"
        assert s.remaining is None
        assert s.spent == 500
    finally:
        db.close()


def test_category_totals_aggregate(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db)
        add_item(db, trip, "food", 300)
        add_item(db, trip, "food", 250)
        add_item(db, trip, "activities", 100)
        db.commit()
        s = budget_service.compute_summary(db, trip)
        assert s.by_category == {"activities": 100.0, "food": 550.0}
    finally:
        db.close()
