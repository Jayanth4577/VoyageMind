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


def _format_recommendations(result_data: dict) -> str | None:
    """Turn a PlacesAgent result into a readable, helpful answer."""
    activities = result_data.get("activities")
    if not activities or not isinstance(activities, list):
        return None
    lines = ["Here are places I found for this trip:"]
    for i, act in enumerate(activities[:8], start=1):
        if not isinstance(act, dict):
            continue
        name = act.get("name") or "Unnamed place"
        bits = []
        if act.get("location_name"):
            bits.append(str(act["location_name"]))
        if act.get("estimated_cost"):
            try:
                bits.append(f"~₹{float(act['estimated_cost']):.0f}")
            except (TypeError, ValueError):
                pass
        if act.get("estimated_duration_minutes"):
            bits.append(f"~{act['estimated_duration_minutes']} min")
        line = f"{i}. **{name}**" + (f" ({', '.join(bits)})" if bits else "")
        if act.get("reason"):
            line += f" — {act['reason']}"
        lines.append(line)
    lines.append(
        "\nWant any of these added to a specific day? Say e.g. "
        "\"add the first one to Day 2\" and I'll propose the change for your approval."
    )
    return "\n".join(lines)


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

    # 4. If the agent produced a full plan, save it — but ONLY onto an empty
    #    itinerary. If the user already built activities, converting the plan
    #    into an approval-required suggestion (golden rule: the user always
    #    approves AI changes to their own itinerary).
    persisted_note = ""
    suggestions = None
    plan_data = result.data.get("plan")
    if isinstance(plan_data, dict) and plan_data.get("days"):
        try:
            from app.agents.plan_persistence import persist_generated_plan
            from app.schemas.agent_schema import GeneratedPlan

            plan = GeneratedPlan.model_validate(plan_data)
            has_user_content = any(
                a.source == "user" and a.user_selected
                for d in trip.days
                for a in d.activities
            )
            if has_user_content:
                changes = []
                for gen_day in plan.days:
                    for act in gen_day.activities:
                        if not (act.name or "").strip():
                            continue
                        changes.append(
                            {
                                "change_type": "add_activity",
                                "target_day": gen_day.day_number,
                                "proposed_data": {
                                    "name": act.name,
                                    "category": act.category,
                                    "location_name": act.location_name,
                                    "latitude": act.latitude,
                                    "longitude": act.longitude,
                                    "start_time": act.start_time,
                                    "end_time": act.end_time,
                                    "duration_minutes": act.duration_minutes,
                                    "estimated_cost": act.estimated_cost,
                                    "weather_sensitive": act.weather_sensitive,
                                    "indoor": act.indoor,
                                    "reason": act.reason,
                                },
                                "problem": "AI drafted a full itinerary",
                                "reason": act.reason or f"Day {gen_day.day_number} activity",
                            }
                        )
                if changes:
                    suggestions = [
                        {
                            "suggestion_id": uuid.uuid4().hex[:12],
                            "changes": changes,
                            "problem": "AI drafted a full itinerary for this trip",
                            "reasoning": plan.reasoning or "",
                            "impact_summary": (
                                f"{len(changes)} activities across "
                                f"{len(plan.days)} days — nothing is added "
                                "until you accept"
                            ),
                        }
                    ]
                    persisted_note = (
                        "\n\nYour trip already has activities, so I won't add "
                        "anything without your approval — review the "
                        "suggestion below and accept or reject it."
                    )
            else:
                persisted = persist_generated_plan(db, trip, plan)
                if persisted:
                    persisted_note = (
                        f"\n\n✅ I've added {persisted} activities to your itinerary — "
                        "open the Itinerary page to see and edit them."
                    )
                    trip.status = "planning"
                    db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Copilot plan persistence failed: %s", exc)

    # 5. Build a genuinely useful reply from structured agent data
    recommendations_text = _format_recommendations(result.data)
    if recommendations_text:
        content = recommendations_text
    elif persisted_note:
        content = (result.reasoning or "Here is your plan.") + persisted_note
    else:
        content = result.reasoning or "Here is what I found."

    # 6. Extract agent-native suggestions if the plan path didn't set any
    suggestion_id = None
    if suggestions is None:
        suggestions = _extract_suggestions(result.data)
    if suggestions:
        sugg = suggestions[0]
        suggestion_id = sugg.get("suggestion_id") or uuid.uuid4().hex[:12]
        sugg["suggestion_id"] = suggestion_id

    # 7. Persist assistant message
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

    # 8. Audit event
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
