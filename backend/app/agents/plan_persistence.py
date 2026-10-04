"""Persist an AI-generated plan into the trip itinerary.

Shared by the /generate endpoint and the copilot so plans created through
either path actually land in the itinerary (they used to differ — the copilot
generated plans that were shown as text but never saved).
"""

from __future__ import annotations

import logging

from app.schemas.activity_schema import ActivityCreate
from app.schemas.agent_schema import GeneratedActivity, GeneratedPlan

logger = logging.getLogger(__name__)


def _activity_create(act: GeneratedActivity, day_id: str) -> ActivityCreate | None:
    name = (act.name or "").strip()
    if not name:
        return None
    return ActivityCreate(
        day_id=day_id,
        name=name[:200],
        category=(act.category or "ACTIVITY").upper()[:40],
        location_name=(act.location_name or "")[:200],
        latitude=act.latitude,
        longitude=act.longitude,
        start_time=act.start_time if act.start_time else "",
        end_time=act.end_time if act.end_time else "",
        duration_minutes=max(0, act.duration_minutes) if act.duration_minutes else None,
        estimated_cost=max(0.0, act.estimated_cost) if act.estimated_cost else 0.0,
        weather_sensitive=act.weather_sensitive,
        indoor=act.indoor,
        source="ai",
        ai_recommended=True,
        user_selected=False,
        confidence=min(1.0, max(0.0, act.confidence)) if act.confidence else 0.5,
        notes=(act.reason or "")[:1000],
    )


def persist_generated_plan(db, trip, plan: GeneratedPlan) -> int:
    """Insert the plan's activities into the trip. Returns the count persisted.

    Each insertion goes through itinerary_service.add_activity, so budget lines
    stay in sync automatically. Invalid activities are skipped with a warning.
    """
    from app.services import itinerary_service

    day_lookup = {d.day_number: d for d in trip.days}
    persisted = 0
    for gen_day in plan.days:
        matching_day = day_lookup.get(gen_day.day_number)
        if matching_day is None:
            logger.warning("plan day %s has no matching itinerary day", gen_day.day_number)
            continue
        for act in gen_day.activities:
            act_create = _activity_create(act, matching_day.id)
            if act_create is None:
                continue
            try:
                itinerary_service.add_activity(db, trip, act_create)
                persisted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to persist activity %s on day %s: %s",
                    act.name,
                    gen_day.day_number,
                    exc,
                )
    return persisted
