"""ConflictService — deterministic schedule validation (spec §2C, §15).

Checks run on real itinerary data only. Transfer feasibility is a labeled
heuristic until Maps MCP routing data is wired in Phase 4; it never claims a
real travel time.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import ItineraryDay, Trip
from app.utils.datetime_utils import gap_minutes, parse_hhmm
from app.utils.geo_utils import haversine_km

HEURISTIC_TRANSFER_MIN_GAP = 30  # minutes assumed between distant stops
HEURISTIC_TRANSFER_MAX_KM = 5.0


@dataclass
class Issue:
    kind: str  # overlap | invalid_time | tight_transfer
    severity: str  # conflict | warning
    message: str
    day_number: int
    activity_ids: list[str] = field(default_factory=list)
    check: str = "deterministic"


def _check_day(day: ItineraryDay) -> list[Issue]:
    issues: list[Issue] = []
    activities = list(day.activities)

    for act in activities:
        start, end = parse_hhmm(act.start_time), parse_hhmm(act.end_time)
        if start is not None and end is not None and end <= start:
            issues.append(
                Issue(
                    kind="invalid_time",
                    severity="conflict",
                    message=(
                        f"{act.name}: end time {act.end_time} is not after "
                        f"start time {act.start_time}"
                    ),
                    day_number=day.day_number,
                    activity_ids=[act.id],
                )
            )

    for a, b in zip(activities, activities[1:], strict=False):
        start_a, end_a = parse_hhmm(a.start_time), parse_hhmm(a.end_time)
        start_b, end_b = parse_hhmm(b.start_time), parse_hhmm(b.end_time)
        if None in (start_a, end_a, start_b, end_b):
            continue
        if start_a < end_b and start_b < end_a:
            issues.append(
                Issue(
                    kind="overlap",
                    severity="conflict",
                    message=(
                        f"{a.name} ({a.start_time}-{a.end_time}) overlaps "
                        f"{b.name} ({b.start_time}-{b.end_time})"
                    ),
                    day_number=day.day_number,
                    activity_ids=[a.id, b.id],
                )
            )
            continue
        gap = gap_minutes(a.end_time, b.start_time)
        if gap is None or gap < 0:
            continue
        if (
            a.latitude is not None
            and a.longitude is not None
            and b.latitude is not None
            and b.longitude is not None
        ):
            km = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
            if km > HEURISTIC_TRANSFER_MAX_KM and gap < HEURISTIC_TRANSFER_MIN_GAP:
                issues.append(
                    Issue(
                        kind="tight_transfer",
                        severity="warning",
                        message=(
                            f"Only {gap} min between {a.name} and {b.name}, "
                            f"which are {km:.1f} km apart (heuristic buffer: "
                            f"{HEURISTIC_TRANSFER_MIN_GAP} min; real routing "
                            f"data arrives in Phase 4)"
                        ),
                        day_number=day.day_number,
                        activity_ids=[a.id, b.id],
                        check="heuristic_transfer_buffer",
                    )
                )
    return issues


def validate_itinerary(db: Session, trip: Trip) -> list[dict]:
    days = (
        db.query(ItineraryDay)
        .filter(ItineraryDay.trip_id == trip.id)
        .order_by(ItineraryDay.day_number)
        .all()
    )
    issues: list[Issue] = []
    for day in days:
        issues.extend(_check_day(day))
    return [
        {
            "kind": i.kind,
            "severity": i.severity,
            "message": i.message,
            "day_number": i.day_number,
            "activity_ids": i.activity_ids,
            "check": i.check,
        }
        for i in issues
    ]
