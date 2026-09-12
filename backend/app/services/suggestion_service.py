"""SuggestionService — applies accepted AI suggestions with full cascade.

On accept: validate → update itinerary → recalc budget → recalc routes
→ recheck weather/conflicts (full cascade, spec §6.4).
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Trip, TripEvent
from app.schemas.activity_schema import ActivityCreate, ActivityUpdate
from app.services import (
    conflict_service,
    itinerary_service,
    route_service,
    weather_service,
)
from app.services.budget_service import compute_summary

logger = get_logger(__name__)


async def apply_suggestion(
    db: Session, trip: Trip, suggestion: dict
) -> dict:
    """Apply a set of suggested changes and run the full cascade."""
    changes = suggestion.get("changes", [])
    applied = 0

    for change in changes:
        try:
            change_type = change.get("change_type", "")
            data = change.get("proposed_data", {})

            if change_type == "add_activity":
                day_num = change.get("target_day")
                day = _find_day(trip, day_num)
                if day:
                    act_data = ActivityCreate(
                        day_id=day.id,
                        name=data.get("name", "Activity")[:200],
                        category=data.get("category", "ACTIVITY")[:40],
                        location_name=data.get("location_name", "")[:200],
                        latitude=data.get("latitude"),
                        longitude=data.get("longitude"),
                        start_time=data.get("start_time", ""),
                        end_time=data.get("end_time", ""),
                        duration_minutes=data.get("duration_minutes"),
                        estimated_cost=data.get("estimated_cost", 0.0),
                        weather_sensitive=data.get("weather_sensitive", False),
                        indoor=data.get("indoor", False),
                        source="ai",
                        ai_recommended=True,
                        user_selected=False,
                        confidence=data.get("confidence", 0.5),
                        notes=data.get("reason", "")[:1000],
                    )
                    itinerary_service.add_activity(db, trip, act_data)
                    applied += 1

            elif change_type == "remove_activity":
                act_id = change.get("target_activity_id")
                if act_id:
                    try:
                        itinerary_service.delete_activity(db, trip, act_id)
                        applied += 1
                    except Exception:
                        pass

            elif change_type == "update_activity":
                act_id = change.get("target_activity_id")
                if act_id and data:
                    update = ActivityUpdate(
                        **{k: v for k, v in data.items() if v is not None}
                    )
                    itinerary_service.update_activity(db, trip, act_id, update)
                    applied += 1

            elif change_type == "move_activity":
                act_id = change.get("target_activity_id")
                target_day_num = data.get("target_day")
                if act_id and target_day_num:
                    day = _find_day(trip, target_day_num)
                    if day:
                        itinerary_service.move_activity(
                            db, trip, act_id, day.id,
                            start_time=data.get("start_time"),
                            end_time=data.get("end_time"),
                        )
                        applied += 1

            elif change_type == "swap_activity":
                # Remove old, add new
                old_id = change.get("target_activity_id")
                if old_id:
                    try:
                        itinerary_service.delete_activity(db, trip, old_id)
                    except Exception:
                        pass
                day_num = change.get("target_day")
                day = _find_day(trip, day_num)
                if day and data.get("name"):
                    act_data = ActivityCreate(
                        day_id=day.id,
                        name=data.get("name", "Activity")[:200],
                        category=data.get("category", "ACTIVITY")[:40],
                        location_name=data.get("location_name", "")[:200],
                        latitude=data.get("latitude"),
                        longitude=data.get("longitude"),
                        start_time=data.get("start_time", ""),
                        end_time=data.get("end_time", ""),
                        duration_minutes=data.get("duration_minutes"),
                        estimated_cost=data.get("estimated_cost", 0.0),
                        weather_sensitive=data.get("weather_sensitive", False),
                        indoor=data.get("indoor", False),
                        source="ai",
                        ai_recommended=True,
                        user_selected=False,
                    )
                    itinerary_service.add_activity(db, trip, act_data)
                    applied += 1

        except Exception as exc:
            logger.warning("Failed to apply change %s: %s", change.get("change_type"), exc)

    # Audit event
    event = TripEvent(
        trip_id=trip.id,
        actor="user",
        kind="suggestion_accepted",
        payload={"applied_changes": applied, "total_changes": len(changes)},
    )
    db.add(event)
    db.commit()

    # Full cascade recalculation
    cascade = await _run_cascade(db, trip)
    cascade["applied_changes"] = applied
    return cascade


async def reject_suggestion(
    db: Session, trip: Trip, suggestion_id: str
) -> dict:
    """Record rejection of a suggestion."""
    event = TripEvent(
        trip_id=trip.id,
        actor="user",
        kind="suggestion_rejected",
        payload={"suggestion_id": suggestion_id},
    )
    db.add(event)
    db.commit()
    return {"status": "rejected", "suggestion_id": suggestion_id}


async def _run_cascade(db: Session, trip: Trip) -> dict:
    """Recalculate budget, routes, weather, conflicts after changes."""
    budget = compute_summary(db, trip)
    try:
        route = await route_service.itinerary_route_report(db, trip)
    except Exception:
        route = {"status": "unavailable"}
    try:
        weather = await weather_service.check_weather_conflicts(db, trip)
    except Exception:
        weather = {"status": "unavailable"}
    conflicts = conflict_service.validate_itinerary(db, trip)

    return {
        "budget": {
            "state": budget.state,
            "spent": budget.spent,
            "total_budget": budget.total_budget,
            "remaining": budget.remaining,
        },
        "route": route,
        "weather": weather,
        "conflicts": conflicts,
    }


def _find_day(trip: Trip, day_number: int | None):
    """Find an itinerary day by number."""
    if day_number is None:
        return None
    for d in trip.days:
        if d.day_number == day_number:
            return d
    return None
