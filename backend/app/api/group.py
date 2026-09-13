"""Group travel endpoints: per-traveler preferences + balanced analysis (spec §20)."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.services import group_service
from app.services.trip_service import get_owned_trip

router = APIRouter(prefix="/trips", tags=["group"])


class PersonPreferences(BaseModel):
    person_name: str = Field(default="", max_length=120)
    preferences: dict[str, float] = Field(default_factory=dict)


class PreferencesIn(BaseModel):
    people: list[PersonPreferences] = Field(max_length=30)


@router.put("/{trip_id}/preferences")
def set_preferences(
    trip_id: str, body: PreferencesIn, user: CurrentUser, db: DbSession
) -> dict:
    trip = get_owned_trip(db, trip_id, user)
    rows = group_service.replace_preferences(db, trip, [p.model_dump() for p in body.people])
    return {"trip_id": trip.id, "saved": len(rows)}


@router.get("/{trip_id}/preferences")
def get_preferences(trip_id: str, user: CurrentUser, db: DbSession) -> list[dict]:
    trip = get_owned_trip(db, trip_id, user)
    rows = group_service.get_preferences(db, trip)
    return [
        {"id": r.id, "person_name": r.person_name, "preferences": r.preferences or {}}
        for r in rows
    ]


@router.get("/{trip_id}/preferences/analysis")
def preference_analysis(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    trip = get_owned_trip(db, trip_id, user)
    return group_service.analysis_for_trip(db, trip)
