"""GroupService tests — deterministic preference aggregation (spec §20)."""
from datetime import date

from app.core.database import SessionLocal
from app.models import Trip, User
from app.services import group_service


def make_trip(db) -> Trip:
    user = User(email=f"grp-{id(db)}@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    trip = Trip(
        owner_id=user.id,
        destination_name="Goa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 3),
    )
    db.add(trip)
    db.commit()
    return trip


def test_replace_and_analyze_preferences(db_tables):
    db = SessionLocal()
    try:
        trip = make_trip(db)
        people = [
            {"person_name": "A", "preferences": {"beach": 1.0, "food": 0.8, "adventure": 0.6}},
            {"person_name": "B", "preferences": {"beach": 0.8, "food": 0.9, "culture": 0.7}},
        ]
        saved = group_service.replace_preferences(db, trip, people)
        assert len(saved) == 2

        rows = group_service.get_preferences(db, trip)
        analysis = group_service.analyze_preferences(trip, rows)

        assert analysis["travelers"] == 2
        # beach: avg(1.0, 0.8) = 0.9 (spec's Beach 90% example)
        assert analysis["interests"]["beach"]["average"] == 0.9
        assert analysis["interests"]["food"]["average"] == 0.85
        # culture only scored by one traveler -> coverage 0.5
        assert analysis["interests"]["culture"]["coverage"] == 0.5
        # balanced weights ranked: beach first
        assert list(analysis["balanced_weights"])[0] == "beach"
        # adventure/culture differ by presence but no >0.5 spread within a shared interest
        assert analysis["conflicts"] == []
    finally:
        db.close()


def test_conflict_detection_on_spread(db_tables):
    db = SessionLocal()
    try:
        trip = make_trip(db)
        people = [
            {"person_name": "A", "preferences": {"nightlife": 1.0}},
            {"person_name": "B", "preferences": {"nightlife": 0.2}},
        ]
        group_service.replace_preferences(db, trip, people)
        analysis = group_service.analysis_for_trip(db, trip)
        assert analysis["interests"]["nightlife"]["min"] == 0.2
        assert analysis["interests"]["nightlife"]["max"] == 1.0
        assert len(analysis["conflicts"]) == 1
        assert analysis["conflicts"][0]["interest"] == "nightlife"
    finally:
        db.close()


def test_replace_deletes_previous_rows(db_tables):
    db = SessionLocal()
    try:
        trip = make_trip(db)
        group_service.replace_preferences(
            db, trip, [{"person_name": "A", "preferences": {"beach": 1.0}}]
        )
        group_service.replace_preferences(
            db, trip, [{"person_name": "B", "preferences": {"food": 0.9}}]
        )
        rows = group_service.get_preferences(db, trip)
        assert len(rows) == 1
        assert rows[0].person_name == "B"
    finally:
        db.close()


def test_scores_clamped_to_valid_range(db_tables):
    db = SessionLocal()
    try:
        trip = make_trip(db)
        rows = group_service.replace_preferences(
            db,
            trip,
            [{"person_name": "A", "preferences": {"beach": 5.0, "food": -1.0}}],
        )
        prefs = rows[0].preferences
        assert prefs["beach"] == 1.0
        assert prefs["food"] == 0.0
    finally:
        db.close()
