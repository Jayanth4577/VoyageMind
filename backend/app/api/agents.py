"""API router for agent operations (spec §5.8, §5.9).

Endpoints:
    POST /trips/{trip_id}/generate     — Full AI auto-plan (Mode A)
    GET  /trips/{trip_id}/recommendations — AI recommendations
"""

from fastapi import APIRouter

from app.agents.context import AgentContext
from app.agents.master_agent import MasterAgent
from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.models import Recommendation, TripEvent
from app.schemas.activity_schema import ActivityCreate
from app.schemas.agent_schema import (
    GeneratedActivity,
    GeneratedPlan,
    GenerateRequest,
    GenerateResponse,
    RecommendationOut,
)
from app.services import itinerary_service
from app.services.trip_service import get_owned_trip

logger = get_logger(__name__)

router = APIRouter(prefix="/trips", tags=["agents"])


def _build_context(db, trip, body: GenerateRequest | None) -> AgentContext:
    """Serialize trip state into an AgentContext for the agent pipeline."""
    trip_data = {
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
        "days": [
            {
                "day_id": d.id,
                "day_number": d.day_number,
                "date": str(d.date) if d.date else None,
            }
            for d in sorted(trip.days, key=lambda d: d.day_number)
        ],
    }

    preferences = body.preferences if body else {}
    if body and body.constraints:
        trip_data["constraints"] = f"{trip_data.get('constraints', '')} {body.constraints}".strip()

    # Group travel: attach the deterministic per-traveler analysis when present
    # so the Planner can generate a balanced plan (spec §20).
    from app.services import group_service

    analysis = group_service.analysis_for_trip(db, trip)
    if analysis["travelers"] > 0:
        trip_data["group_preferences"] = analysis

    return AgentContext(
        trip_id=trip.id,
        trip_data=trip_data,
        preferences=preferences,
        request="generate",
    )


def _parse_plan(result_data: dict) -> GeneratedPlan | None:
    """Extract a GeneratedPlan from agent result data, tolerating multiple formats."""
    raw_plan = result_data.get("plan")
    if raw_plan is None:
        return None
    if isinstance(raw_plan, GeneratedPlan):
        return raw_plan
    if isinstance(raw_plan, dict):
        try:
            return GeneratedPlan.model_validate(raw_plan)
        except Exception:
            return None
    return None


def _safe_activity_create(act: GeneratedActivity, day_id: str) -> ActivityCreate | None:
    """Build an ActivityCreate from a GeneratedActivity, skipping invalid ones."""
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


@router.post("/{trip_id}/generate")
async def generate_plan(
    trip_id: str,
    user: CurrentUser,
    db: DbSession,
    body: GenerateRequest | None = None,
) -> GenerateResponse:
    """Full AI auto-plan generation (Mode A).

    Invokes the MasterAgent → PlannerAgent pipeline to generate a complete
    daily itinerary from trip inputs.  Generated activities are persisted into
    the trip's itinerary_days via ``itinerary_service.add_activity`` (which
    auto-syncs budget items).  The plan is editable afterwards (Mode B).
    """
    trip = get_owned_trip(db, trip_id, user)
    context = _build_context(db, trip, body)

    master = MasterAgent()
    result = await master.run(context)

    plan = _parse_plan(result.data)

    # Persist generated activities
    persisted_count = 0
    if plan and plan.days:
        day_lookup = {d.day_number: d for d in trip.days}
        for gen_day in plan.days:
            matching_day = day_lookup.get(gen_day.day_number)
            if not matching_day:
                continue
            for act in gen_day.activities:
                act_create = _safe_activity_create(act, matching_day.id)
                if act_create is None:
                    continue
                try:
                    itinerary_service.add_activity(db, trip, act_create)
                    persisted_count += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to persist activity %s on day %s: %s",
                        act.name,
                        gen_day.day_number,
                        exc,
                    )

    # Audit event
    event = TripEvent(
        trip_id=trip.id,
        actor="ai",
        kind="agent_run",
        payload={
            "agent": "MasterAgent",
            "status": result.status,
            "activities_persisted": persisted_count,
            "tool_calls_count": len(result.tool_calls),
        },
    )
    db.add(event)

    # Update trip status
    trip.status = "planning"
    db.commit()

    return GenerateResponse(
        trip_id=trip.id,
        status=result.status,
        plan=plan,
        transport_options=_safe_list(result.data.get("transport")),
        accommodation_options=_safe_list(result.data.get("accommodation")),
        weather_summary=result.data.get("weather") or {},
        budget_estimate={},
        risks=[],
        contingencies=[],
        tool_calls_count=len(result.tool_calls),
        reasoning=result.reasoning,
    )


def _safe_list(value) -> list[dict]:
    """Coerce agent result data into a list of dicts."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


@router.get("/{trip_id}/recommendations")
def get_recommendations(trip_id: str, user: CurrentUser, db: DbSession) -> list[RecommendationOut]:
    """Get AI recommendations for a trip."""
    trip = get_owned_trip(db, trip_id, user)
    recs = db.query(Recommendation).filter(Recommendation.trip_id == trip.id).all()
    return [RecommendationOut.model_validate(r) for r in recs]
