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


async def resolve_trip_coordinates(db, trip: Trip) -> tuple[float, float] | None:
    """Trip destination coordinates, geocoded and persisted on first use."""
    if trip.destination_lat is not None and trip.destination_lng is not None:
        return trip.destination_lat, trip.destination_lng

    geo = await travel_mcp.maps.geocode_place(trip.destination_name)
    results = geo.get("results") or []
    if not results:
        return None
    top = results[0]
    latitude, longitude = top["latitude"], top["longitude"]
    trip.destination_lat, trip.destination_lng = latitude, longitude
    db.commit()
    return latitude, longitude
