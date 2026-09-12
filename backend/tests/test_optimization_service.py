"""OptimizationService budget plan — deterministic savings candidates (spec §7)."""
from datetime import date

from app.core.database import SessionLocal
from app.models import BudgetItem, Trip, User
from app.services import optimization_service


def seed(db, budget, items):
    user = User(email=f"opt-{id(db)}@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    trip = Trip(
        owner_id=user.id,
        destination_name="Goa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 3),
        total_budget=budget,
        currency="INR",
    )
    db.add(trip)
    db.flush()
    for category, label, amount in items:
        db.add(BudgetItem(trip_id=trip.id, category=category, label=label, amount=amount))
    db.commit()
    return trip


def test_no_budget(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db, None, [("food", "Dinner", 500)])
        plan = optimization_service.budget_savings_plan(db, trip)
        assert plan["status"] == "no_budget"
    finally:
        db.close()


def test_on_track(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db, 50000, [("food", "Dinner", 5000)])
        plan = optimization_service.budget_savings_plan(db, trip)
        assert plan["status"] == "on_track"
    finally:
        db.close()


def test_over_budget_candidates_use_category_median(db_tables):
    db = SessionLocal()
    try:
        # Spent 22500 vs budget 20000 -> over by 2500
        trip = seed(
            db,
            20000,
            [
                ("accommodation", "Luxury Hotel", 10000),
                ("accommodation", "Mid Hotel", 5000),
                ("accommodation", "Budget Hotel", 2500),
                ("food", "Dinner", 3000),
                ("transport", "Flight", 2000),
            ],
        )
        plan = optimization_service.budget_savings_plan(db, trip)
        assert plan["status"] == "over_budget"
        assert plan["over_budget_amount"] == 2500

        candidates = plan["candidates"]
        # Luxury Hotel: median of the others [5000, 2500] = 3750 -> saving 6250 (top)
        top = candidates[0]
        assert top["label"] == "Luxury Hotel"
        assert top["potential_saving"] == 6250.0
        assert top["target_amount"] == 3750.0

        # Mid Hotel: median of the others [10000, 2500] = 6250 -> no saving (below median)
        assert all(c["label"] != "Mid Hotel" or c["potential_saving"] <= 0 for c in candidates)

        # Plan stops once the shortfall is covered
        assert plan["covers_shortfall"] is True
        assert plan["potential_total_saving"] <= plan["over_budget_amount"] + 0.01
    finally:
        db.close()


def test_single_line_categories_go_to_review_list(db_tables):
    db = SessionLocal()
    try:
        trip = seed(db, 5000, [("transport", "Flight", 4000), ("food", "Dinner", 3000)])
        plan = optimization_service.budget_savings_plan(db, trip)
        assert plan["status"] == "over_budget"
        assert plan["candidates"] == []  # no same-category comparison possible
        review = {r["label"] for r in plan["review_largest_lines"]}
        assert review == {"Flight", "Dinner"}
    finally:
        db.close()
