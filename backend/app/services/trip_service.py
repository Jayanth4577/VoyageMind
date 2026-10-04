"""TripService — shared trip loading, ownership enforcement, coordinate resolution."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.mcp.travel_mcp import travel_mcp
from app.models import Trip, User


def get_owned_trip(db, trip_id: str, user: User) -> Trip:
    trip = db.scalar(
        select(Trip)
        .options(joinedload(Trip.days))
        .where(Trip.id == trip_id, Trip.owner_id == user.id)
    )
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    return trip


# The mock geocoder's synthetic coordinates. If a trip's stored destination
# equals these while its name clearly isn't that place, the row was poisoned
# by an old fallback bug (the "every map shows Goa" issue) — re-geocode it.
_MOCK_COORDS = (15.2993, 74.124)


async def resolve_trip_coordinates(db, trip: Trip) -> tuple[float, float] | None:
    """Trip destination coordinates, geocoded and persisted on first use.

    Synthetic (mock) coordinates are used for the current response but NEVER
    persisted — fake coords on the trip row would send every map to the wrong
    place.
    """
    stored_is_poisoned = (
        trip.destination_lat is not None
        and trip.destination_lng is not None
        and (trip.destination_lat, trip.destination_lng) == _MOCK_COORDS
        and "goa" not in (trip.destination_name or "").lower()
    )
    if (
        trip.destination_lat is not None
        and trip.destination_lng is not None
        and not stored_is_poisoned
    ):
        return trip.destination_lat, trip.destination_lng

    geo = await travel_mcp.maps.geocode_place(trip.destination_name)
    results = geo.get("results") or []
    if not results:
        return None
    top = results[0]
    latitude, longitude = top["latitude"], top["longitude"]
    if not geo.get("is_mock"):
        trip.destination_lat, trip.destination_lng = latitude, longitude
        db.commit()
    return latitude, longitude
