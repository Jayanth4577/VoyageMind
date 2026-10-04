"""Discovery endpoints: nearby destinations, transport options, stays (spec §4/§11).

All data comes from the Travel MCP facades (real APIs or labeled demo), and
booking is handed off to free public sites via deep links — VoyageMind itself
never takes payments.
"""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.mcp.travel_mcp import travel_mcp
from app.services.trip_service import get_owned_trip, resolve_trip_coordinates

router = APIRouter(prefix="/trips", tags=["discover"])


@router.get("/{trip_id}/nearby-destinations")
async def nearby_destinations(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Real towns/villages worth a day trip around the destination."""
    trip = get_owned_trip(db, trip_id, user)
    coords = await resolve_trip_coordinates(db, trip)
    if coords is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Could not resolve destination '{trip.destination_name}'",
        )
    latitude, longitude = coords
    result = await travel_mcp.maps.find_nearby_destinations(
        latitude, longitude, exclude=trip.destination_name
    )
    dest_lower = trip.destination_name.lower()
    results = [
        r
        for r in (result.get("results") or [])
        if (r.get("name") or "").strip().lower() != dest_lower
    ]
    for r in results:
        r["maps_url"] = (
            f"https://www.openstreetmap.org/?mlat={r.get('latitude')}"
            f"&mlon={r.get('longitude')}#map=12/{r.get('latitude')}/{r.get('longitude')}"
        )
    return {
        **result,
        "results": results,
        "destination": trip.destination_name,
    }


@router.get("/{trip_id}/transport-options")
async def transport_options(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Transport options for origin -> destination on the start date."""
    trip = get_owned_trip(db, trip_id, user)
    if not trip.origin_name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This trip has no origin set — edit the trip to add one",
        )
    result = await travel_mcp.flights.search_transport(
        trip.origin_name, trip.destination_name, trip.start_date.isoformat()
    )
    return {
        **result,
        "query": {
            "origin": trip.origin_name,
            "destination": trip.destination_name,
            "date": trip.start_date.isoformat(),
        },
    }


@router.get("/{trip_id}/stays")
async def stay_options(trip_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Stay options at the destination for the trip's dates."""
    trip = get_owned_trip(db, trip_id, user)
    result = await travel_mcp.flights.search_stays(
        trip.destination_name,
        trip.start_date.isoformat(),
        trip.end_date.isoformat(),
        guests=max(1, trip.num_travelers),
    )
    return {**result, "guests": max(1, trip.num_travelers)}
