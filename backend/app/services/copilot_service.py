"""CopilotService — context-aware AI assistant for trip planning.

Handles copilot chat messages, delegates to agents, and extracts
structured suggestions from agent responses.
"""

import uuid

from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.master_agent import MasterAgent
from app.core.logging import get_logger
from app.models import CopilotMessage, Trip, TripEvent

logger = get_logger(__name__)


def _build_trip_data(trip: Trip) -> dict:
    """Serialize current trip state for agent context."""
    days_data = []
    for d in sorted(trip.days, key=lambda x: x.day_number):
        activities = []
        for a in sorted(d.activities, key=lambda x: x.position):
            activities.append({
                "id": a.id,
                "name": a.name,
                "category": a.category,
                "location_name": a.location_name,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "start_time": a.start_time or "",
                "end_time": a.end_time or "",
                "duration_minutes": a.duration_minutes,
                "estimated_cost": float(a.estimated_cost or 0),
                "weather_sensitive": a.weather_sensitive,
                "indoor": a.indoor,
            })
        days_data.append({
            "day_id": d.id,
            "day_number": d.day_number,
            "date": str(d.date) if d.date else None,
            "activities": activities,
        })

    return {
        "id": trip.id,
        "origin_name": trip.origin_name,
        "destination_name": trip.destination_name,
        "destination_lat": trip.destination_lat,
        "destination_lng": trip.destination_lng,
        "start_date": str(trip.start_date) if trip.start_date else None,
        "end_date": str(trip.end_date) if trip.end_date else None,
        "num_travelers": trip.num_travelers,
        "total_budget": trip.total_budget,
        "currency": trip.currency,
        "trip_style": trip.trip_style,
        "constraints": trip.constraints,
        "preferences": trip.preferences or {},
        "days": days_data,
    }


def _extract_suggestions(result_data: dict) -> list[dict] | None:
    """Extract structured suggestions from agent result."""
    # Agents may return suggestions in different formats
    suggestions = result_data.get("suggestions")
    if suggestions:
        return suggestions if isinstance(suggestions, list) else [suggestions]

    # Check for savings suggestions from budget agent
    savings = result_data.get("savings_suggestions")
    if savings:
        return [{
            "suggestion_id": uuid.uuid4().hex[:12],
            "changes": [{
                "change_type": "update_activity",
                "proposed_data": s,
                "problem": "Over budget",
                "reason": s.get("rationale", ""),
                "impact": f"Save {s.get('saving_amount', 0)}",
            } for s in savings],
            "problem": "Budget optimization needed",
            "reasoning": result_data.get("reasoning", ""),
        }]

    return None


async def handle_message(
    db: Session, trip: Trip, message: str
) -> dict:
    """Process a copilot message and return AI response."""
    # 1. Persist user message
    user_msg = CopilotMessage(
        trip_id=trip.id,
        role="user",
        content=message,
        data={},
    )
    db.add(user_msg)
    db.flush()

    # 2. Build context from current trip state
    trip_data = _build_trip_data(trip)
    context = AgentContext(
        trip_id=trip.id,
        trip_data=trip_data,
        preferences=trip.preferences or {},
        request=message,
    )

    # 3. Run agent
    try:
        master = MasterAgent()
        result = await master.run(context)
    except Exception as exc:
        logger.error("Copilot agent error: %s", exc)
        result_content = (
            "I encountered an error processing your request. "
            "Please try again."
        )
        assistant_msg = CopilotMessage(
            trip_id=trip.id,
            role="assistant",
            content=result_content,
            data={"error": str(exc)},
        )
        db.add(assistant_msg)
        db.commit()
        return {
            "message": _msg_to_dict(assistant_msg),
            "suggestions": None,
        }

    # 4. Extract suggestions
    suggestions = _extract_suggestions(result.data)
    suggestion_id = None
    if suggestions:
        sugg = suggestions[0]
        suggestion_id = sugg.get("suggestion_id") or uuid.uuid4().hex[:12]
        sugg["suggestion_id"] = suggestion_id

    # 5. Build response content
    content = result.reasoning or "Here is what I found."

    # 6. Persist assistant message
    msg_data = {
        "agent": result.agent_name,
        "status": result.status,
        "tool_calls_count": len(result.tool_calls),
    }
    if suggestion_id:
        msg_data["suggestion_id"] = suggestion_id
    if suggestions:
        msg_data["suggestions"] = suggestions

    assistant_msg = CopilotMessage(
        trip_id=trip.id,
        role="assistant",
        content=content,
        data=msg_data,
    )
    db.add(assistant_msg)

    # 7. Audit event
    event = TripEvent(
        trip_id=trip.id,
        actor="ai",
        kind="copilot_response",
        payload={
            "agent": result.agent_name,
            "status": result.status,
            "has_suggestions": bool(suggestions),
        },
    )
    db.add(event)
    db.commit()
    db.refresh(assistant_msg)

    return {
        "message": _msg_to_dict(assistant_msg),
        "suggestions": suggestions,
    }


def get_history(
    db: Session, trip: Trip, limit: int = 50
) -> list[dict]:
    """Get copilot message history for a trip."""
    msgs = (
        db.query(CopilotMessage)
        .filter(CopilotMessage.trip_id == trip.id)
        .order_by(CopilotMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    return [_msg_to_dict(m) for m in msgs]


def _msg_to_dict(msg: CopilotMessage) -> dict:
    return {
        "id": msg.id,
        "trip_id": msg.trip_id,
        "role": msg.role,
        "content": msg.content,
        "data": msg.data or {},
        "created_at": str(msg.created_at),
    }
