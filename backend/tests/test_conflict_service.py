"""ConflictService unit tests — overlap / invalid time / tight transfer."""
from datetime import date

from app.core.database import SessionLocal
from app.models import Activity, ItineraryDay, Trip, User
from app.services.conflict_service import validate_itinerary


def make_trip_with_day(db) -> tuple[Trip, ItineraryDay]:
    user = User(email=f"conflict-{id(db)}@example.com", hashed_password="x")
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
    return trip, day


def add_activity(db, day, name, start, end, lat=None, lng=None, pos=0):
    act = Activity(
        trip_id=day.trip_id,
        day_id=day.id,
        name=name,
        category="ACTIVITY",
        start_time=start,
        end_time=end,
        latitude=lat,
        longitude=lng,
        position=pos,
    )
    db.add(act)
    db.flush()
    return act


def kinds(issues):
    return sorted(i["kind"] for i in issues)


def test_no_issues_on_clean_day(db_tables):
    db = SessionLocal()
    try:
        trip, day = make_trip_with_day(db)
        add_activity(db, day, "Baga Beach", "10:00", "12:00", 15.55, 73.75, pos=0)
        add_activity(db, day, "Aguada Fort", "13:00", "14:30", 15.55, 73.75, pos=1)
        db.commit()
        assert validate_itinerary(db, trip) == []
    finally:
        db.close()


def test_overlap_detected(db_tables):
    db = SessionLocal()
    try:
        trip, day = make_trip_with_day(db)
        a = add_activity(db, day, "Baga Beach", "10:00", "12:00", pos=0)
        b = add_activity(db, day, "Panaji Walk", "11:00", "12:30", pos=1)
        db.commit()
        issues = validate_itinerary(db, trip)
        assert kinds(issues) == ["overlap"]
        assert set(issues[0]["activity_ids"]) == {a.id, b.id}
        assert issues[0]["severity"] == "conflict"
    finally:
        db.close()


def test_end_before_start_invalid(db_tables):
    db = SessionLocal()
    try:
        trip, day = make_trip_with_day(db)
        add_activity(db, day, "Bad Timing", "15:00", "14:00", pos=0)
        db.commit()
        issues = validate_itinerary(db, trip)
        assert kinds(issues) == ["invalid_time"]
        assert issues[0]["severity"] == "conflict"
    finally:
        db.close()


def test_tight_transfer_warning_between_distant_points(db_tables):
    db = SessionLocal()
    try:
        trip, day = make_trip_with_day(db)
        # ~30km apart in straight line, only 15 min gap -> heuristic warning
        add_activity(db, day, "South Beach", "10:00", "11:00", 15.0, 73.8, pos=0)
        add_activity(db, day, "North Fort", "11:15", "12:30", 15.4, 73.8, pos=1)
        db.commit()
        issues = validate_itinerary(db, trip)
        assert kinds(issues) == ["tight_transfer"]
        assert issues[0]["severity"] == "warning"
        assert issues[0]["check"] == "heuristic_transfer_buffer"
    finally:
        db.close()


def test_close_stops_without_gap_are_fine(db_tables):
    db = SessionLocal()
    try:
        trip, day = make_trip_with_day(db)
        add_activity(db, day, "Cafe A", "10:00", "11:00", 15.27, 73.96, pos=0)
        add_activity(db, day, "Cafe B", "11:05", "12:00", 15.27, 73.97, pos=1)
        db.commit()
        assert validate_itinerary(db, trip) == []
    finally:
        db.close()


def test_issues_across_multiple_days(db_tables):
    db = SessionLocal()
    try:
        trip, day1 = make_trip_with_day(db)
        day2 = ItineraryDay(trip_id=trip.id, day_number=2, date=date(2026, 10, 2))
        db.add(day2)
        db.flush()
        add_activity(db, day1, "A", "10:00", "11:00", pos=0)
        add_activity(db, day1, "B", "10:30", "11:30", pos=1)  # overlap day 1
        add_activity(db, day2, "C", "09:00", "08:00", pos=0)  # invalid day 2
        db.commit()
        issues = validate_itinerary(db, trip)
        assert kinds(issues) == ["invalid_time", "overlap"]
        assert {i["day_number"] for i in issues} == {1, 2}
    finally:
        db.close()
