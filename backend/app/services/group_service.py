"""GroupService — per-traveler preferences and balanced-plan analysis (spec §20).

The overlap/conflict analysis is deterministic: per-interest averages across
travelers, agreement spread, and a balanced weighting the Planner Agent can use.
"""
from sqlalchemy.orm import Session

from app.models import Trip, TripPreference


def replace_preferences(db: Session, trip: Trip, people: list[dict]) -> list[TripPreference]:
    """Replace all per-traveler preference rows for the trip."""
    db.query(TripPreference).filter(TripPreference.trip_id == trip.id).delete()
    saved = []
    for person in people:
        prefs = person.get("preferences") or {}
        clean = {
            str(k).strip().lower()[:40]: max(0.0, min(1.0, float(v)))
            for k, v in prefs.items()
            if isinstance(v, (int, float))
        }
        row = TripPreference(
            trip_id=trip.id,
            person_name=(person.get("person_name") or "").strip()[:120],
            preferences=clean,
        )
        db.add(row)
        saved.append(row)
    db.commit()
    return saved


def get_preferences(db: Session, trip: Trip) -> list[TripPreference]:
    return (
        db.query(TripPreference)
        .filter(TripPreference.trip_id == trip.id)
        .order_by(TripPreference.person_name)
        .all()
    )


def analyze_preferences(trip: Trip, rows: list[TripPreference]) -> dict:
    """Deterministic per-interest aggregate across travelers (spec §20 example)."""
    people = [
        {"person_name": r.person_name, "preferences": r.preferences or {}}
        for r in rows
    ]
    interest_scores: dict[str, list[float]] = {}
    for person in people:
        for interest, score in person["preferences"].items():
            interest_scores.setdefault(interest, []).append(float(score))

    aggregate: dict[str, dict] = {}
    for interest, scores in interest_scores.items():
        avg = sum(scores) / len(scores)
        aggregate[interest] = {
            "average": round(avg, 3),
            "coverage": round(len(scores) / len(people), 3) if people else 0.0,
            "min": round(min(scores), 3),
            "max": round(max(scores), 3),
            # High average + low spread = strong group overlap
            "consensus": round(avg * (1 - (max(scores) - min(scores))), 3),
        }

    # Ranked list the planner can consume as balanced weights
    balanced_weights = {
        interest: data["average"]
        for interest, data in sorted(
            aggregate.items(), key=lambda kv: kv[1]["average"], reverse=True
        )
    }

    conflicts = [
        {
            "interest": interest,
            "detail": (
                f"Score spread {data['min']}–{data['max']} across travelers"
            ),
        }
        for interest, data in aggregate.items()
        if data["max"] - data["min"] >= 0.5
    ]

    return {
        "trip_id": trip.id,
        "travelers": len(people),
        "people": people,
        "interests": aggregate,
        "balanced_weights": balanced_weights,
        "conflicts": conflicts,
    }


def analysis_for_trip(db: Session, trip: Trip) -> dict:
    return analyze_preferences(trip, get_preferences(db, trip))
