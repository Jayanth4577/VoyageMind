"""Weather endpoints (spec §24). Data flows through the Travel MCP facades."""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.mcp.travel_mcp import travel_mcp
from app.services.trip_service import get_owned_trip, resolve_trip_coordinates

router = APIRouter(tags=["weather"])


@router.get("/trips/{trip_id}/weather")
async def get_trip_weather(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    trip = get_owned_trip(db, trip_id, user)
    days = min(7, (trip.end_date - trip.start_date).days + 1)

    coordinates = await resolve_trip_coordinates(db, trip)
    if coordinates is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Could not resolve destination '{trip.destination_name}' to coordinates",
        )
    latitude, longitude = coordinates

    forecast = await travel_mcp.weather.get_weather(latitude, longitude, days)
    return {**forecast, "resolved_destination": {"latitude": latitude, "longitude": longitude}}
