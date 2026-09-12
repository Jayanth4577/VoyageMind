"""API router for copilot, suggestions, contingencies, and what-if (Phase 6).

Endpoints:
    POST /trips/{trip_id}/copilot         — Send copilot message
    GET  /trips/{trip_id}/copilot/history  — Get chat history
    POST /trips/{trip_id}/suggestions/{suggestion_id}/action — Accept/reject suggestion
    GET  /trips/{trip_id}/contingencies    — List contingencies
    POST /trips/{trip_id}/contingencies/{id}/action — Accept/dismiss/activate
    POST /trips/{trip_id}/simulate        — What-if simulation
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.schemas.copilot_schema import (
    ContingencyAction,
    ContingencyOut,
    CopilotRequest,
    SuggestionAction,
    SuggestionActionResponse,
    WhatIfRequest,
    WhatIfResult,
)
from app.services import (
    contingency_service,
    copilot_service,
    suggestion_service,
    whatif_service,
)
from app.services.trip_service import get_owned_trip

logger = get_logger(__name__)

router = APIRouter(prefix="/trips", tags=["copilot"])


@router.post("/{trip_id}/copilot")
async def send_copilot_message(
    trip_id: str,
    body: CopilotRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Send a message to the AI copilot."""
    trip = get_owned_trip(db, trip_id, user)
    return await copilot_service.handle_message(db, trip, body.message)


@router.get("/{trip_id}/copilot/history")
def get_copilot_history(
    trip_id: str,
    user: CurrentUser,
    db: DbSession,
    limit: int = 50,
) -> list[dict]:
    """Get copilot chat history."""
    trip = get_owned_trip(db, trip_id, user)
    return copilot_service.get_history(db, trip, limit=limit)


@router.post("/{trip_id}/suggestions/{suggestion_id}/action")
async def handle_suggestion(
    trip_id: str,
    suggestion_id: str,
    body: SuggestionAction,
    user: CurrentUser,
    db: DbSession,
) -> SuggestionActionResponse:
    """Accept, reject, or edit a suggestion."""
    trip = get_owned_trip(db, trip_id, user)

    if body.action == "reject":
        await suggestion_service.reject_suggestion(db, trip, suggestion_id)
        return SuggestionActionResponse(status="rejected", applied_changes=0)

    if body.action == "accept":
        # Find the suggestion from copilot history
        history = copilot_service.get_history(db, trip)
        suggestion = None
        for msg in history:
            data = msg.get("data", {})
            if data.get("suggestion_id") == suggestion_id:
                suggestions = data.get("suggestions", [])
                if suggestions:
                    suggestion = suggestions[0]
                break

        if suggestion is None:
            return SuggestionActionResponse(status="not_found", applied_changes=0)

        result = await suggestion_service.apply_suggestion(db, trip, suggestion)
        return SuggestionActionResponse(
            status="applied",
            applied_changes=result.get("applied_changes", 0),
            cascade=result,
        )

    return SuggestionActionResponse(status="unsupported", applied_changes=0)


@router.get("/{trip_id}/contingencies")
def list_contingencies(
    trip_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[ContingencyOut]:
    """List contingency plans."""
    trip = get_owned_trip(db, trip_id, user)
    items = contingency_service.get_contingencies(db, trip)
    return [ContingencyOut.model_validate(c) for c in items]


@router.post("/{trip_id}/contingencies/{contingency_id}/action")
def handle_contingency_action(
    trip_id: str,
    contingency_id: str,
    body: ContingencyAction,
    user: CurrentUser,
    db: DbSession,
) -> ContingencyOut:
    """Accept, dismiss, or activate a contingency."""
    trip = get_owned_trip(db, trip_id, user)
    c = contingency_service.update_status(db, trip, contingency_id, body.action)
    return ContingencyOut.model_validate(c)


@router.post("/{trip_id}/simulate")
async def simulate_whatif(
    trip_id: str,
    body: WhatIfRequest,
    user: CurrentUser,
    db: DbSession,
) -> WhatIfResult:
    """Run a what-if simulation."""
    trip = get_owned_trip(db, trip_id, user)
    result = await whatif_service.simulate(db, trip, body.scenario, body.parameters)
    return WhatIfResult.model_validate(result)
