"""ContingencyService — manages contingency tree lifecycle.

Creates contingency records from agent results or what-if simulations,
and handles accept/dismiss/activate state transitions.
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Contingency, Trip, TripEvent

logger = get_logger(__name__)


def create_contingency(
    db: Session, trip: Trip, data: dict
) -> Contingency:
    """Create a contingency record from agent/simulation data."""
    contingency = Contingency(
        trip_id=trip.id,
        plan_level=data.get("plan_level", "B")[:2],
        trigger=data.get("trigger", "OTHER")[:40],
        condition=data.get("condition", "")[:300],
        affected_activity_ids=data.get("affected_activity_ids", []),
        fallback_plan=data.get("fallback_steps", data.get("fallback_plan", [])),
        budget_impact=data.get("budget_impact"),
        time_impact_minutes=data.get("time_impact_minutes"),
        confidence=data.get("confidence"),
        reason=data.get("reason", "")[:1000],
        requires_user_approval=data.get("requires_user_approval", True),
        status="proposed",
    )
    db.add(contingency)
    db.flush()
    return contingency


def create_from_agent_result(
    db: Session, trip: Trip, agent_data: dict
) -> list[Contingency]:
    """Create contingencies from a ContingencyAgent result."""
    contingencies_data = agent_data.get("contingencies", [])
    created = []
    for c_data in contingencies_data:
        c = create_contingency(db, trip, c_data)
        created.append(c)
    if created:
        db.commit()
    return created


def get_contingencies(
    db: Session, trip: Trip
) -> list[Contingency]:
    """Get all contingencies for a trip."""
    return (
        db.query(Contingency)
        .filter(Contingency.trip_id == trip.id)
        .order_by(Contingency.created_at.desc())
        .all()
    )


def update_status(
    db: Session, trip: Trip, contingency_id: str, action: str
) -> Contingency:
    """Accept, dismiss, or activate a contingency."""
    contingency = db.get(Contingency, contingency_id)
    if contingency is None or contingency.trip_id != trip.id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Contingency not found",
        )

    valid_transitions = {
        "accept": "accepted",
        "dismiss": "dismissed",
        "activate": "activated",
    }
    new_status = valid_transitions.get(action)
    if not new_status:
        from fastapi import HTTPException, status
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid action: {action}",
        )

    contingency.status = new_status

    event = TripEvent(
        trip_id=trip.id,
        actor="user",
        kind=f"contingency_{action}",
        payload={
            "contingency_id": contingency_id,
            "trigger": contingency.trigger,
            "plan_level": contingency.plan_level,
        },
    )
    db.add(event)
    db.commit()
    db.refresh(contingency)
    return contingency
