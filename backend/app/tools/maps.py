"""Maps tool — geo-clustering and distance calculations.

Uses OpenStreetMap / Nominatim for geocoding and attraction lookup.
Haversine formula for distance computation (no API key required).
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Tool schema for Nova structured tool calling
MAPS_TOOL_SCHEMA: dict[str, Any] = {
    "toolSpec": {
        "name": "get_nearby_attractions",
        "description": "Find attractions near a destination and compute distances.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["destination"],
            }
        },
    }
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in km between two lat/lon points."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MapsTool:
    """Geo-clustering and distance tool using OpenStreetMap."""

    async def get_nearby_attractions(
        self,
        destination: str,
        latitude: float = 0.0,
        longitude: float = 0.0,
        radius_km: float = 10.0,
    ) -> list[dict[str, Any]]:
        """Fetch notable attractions near the destination."""
        settings = get_settings()

        if settings.mock_mode:
            return self._mock_attractions(destination)

        return await self._fetch_attractions_osm(destination, latitude, longitude, radius_km)

    async def compute_distances(
        self,
        origin_lat: float,
        origin_lon: float,
        attractions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Compute distances from a point (hotel) to each attraction."""
        results = []
        for attr in attractions:
            dist = _haversine(
                origin_lat,
                origin_lon,
                attr.get("latitude", 0),
                attr.get("longitude", 0),
            )
            results.append({
                "attraction_name": attr.get("name", "Unknown"),
                "distance_km": round(dist, 2),
            })
        return results

    # ------------------------------------------------------------------
    # Mock
    # ------------------------------------------------------------------

    def _mock_attractions(self, destination: str) -> list[dict[str, Any]]:
        """Return a curated set of mock attractions by city."""
        mock_db: dict[str, list[dict[str, Any]]] = {
            "paris": [
                {"name": "Eiffel Tower", "latitude": 48.8584, "longitude": 2.2945, "category": "landmark"},
                {"name": "Louvre Museum", "latitude": 48.8606, "longitude": 2.3376, "category": "museum"},
                {"name": "Notre-Dame", "latitude": 48.8530, "longitude": 2.3499, "category": "landmark"},
                {"name": "Sacré-Cœur", "latitude": 48.8867, "longitude": 2.3431, "category": "landmark"},
                {"name": "Musée d'Orsay", "latitude": 48.8600, "longitude": 2.3266, "category": "museum"},
            ],
            "london": [
                {"name": "Big Ben", "latitude": 51.5007, "longitude": -0.1246, "category": "landmark"},
                {"name": "Tower of London", "latitude": 51.5081, "longitude": -0.0759, "category": "landmark"},
                {"name": "British Museum", "latitude": 51.5194, "longitude": -0.1270, "category": "museum"},
                {"name": "Buckingham Palace", "latitude": 51.5014, "longitude": -0.1419, "category": "landmark"},
                {"name": "London Eye", "latitude": 51.5033, "longitude": -0.1196, "category": "landmark"},
            ],
            "tokyo": [
                {"name": "Senso-ji Temple", "latitude": 35.7148, "longitude": 139.7967, "category": "temple"},
                {"name": "Tokyo Tower", "latitude": 35.6586, "longitude": 139.7454, "category": "landmark"},
                {"name": "Shibuya Crossing", "latitude": 35.6595, "longitude": 139.7004, "category": "landmark"},
                {"name": "Meiji Shrine", "latitude": 35.6764, "longitude": 139.6993, "category": "temple"},
                {"name": "Tsukiji Market", "latitude": 35.6654, "longitude": 139.7707, "category": "market"},
            ],
        }
        dest_lower = destination.lower()
        for key, attractions in mock_db.items():
            if key in dest_lower:
                logger.info("Mock attractions: %d for %s", len(attractions), destination)
                return attractions

        # Generic fallback
        return [
            {"name": f"{destination} City Center", "latitude": 0, "longitude": 0, "category": "landmark"},
        ]

    # ------------------------------------------------------------------
    # Live OSM / Nominatim
    # ------------------------------------------------------------------

    async def _fetch_attractions_osm(
        self,
        destination: str,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[dict[str, Any]]:
        """Query OpenStreetMap Overpass API for tourism POIs."""
        import httpx

        radius_m = int(radius_km * 1000)

        if latitude == 0.0 and longitude == 0.0:
            latitude, longitude = await self._geocode(destination)

        query = f"""
        [out:json][timeout:10];
        node["tourism"~"attraction|museum|viewpoint"](around:{radius_m},{latitude},{longitude});
        out body 10;
        """

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
            )
            resp.raise_for_status()
            data = resp.json()

        attractions = []
        for el in data.get("elements", []):
            attractions.append({
                "name": el.get("tags", {}).get("name", "Unnamed"),
                "latitude": el.get("lat", 0),
                "longitude": el.get("lon", 0),
                "category": el.get("tags", {}).get("tourism", "attraction"),
            })

        logger.info("OSM attractions: %d near %s", len(attractions), destination)
        return attractions

    async def _geocode(self, destination: str) -> tuple[float, float]:
        """Geocode a place name to lat/lon via Nominatim."""
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": destination, "format": "json", "limit": 1},
                headers={"User-Agent": "VoyageMind/1.0"},
            )
            resp.raise_for_status()
            results = resp.json()

        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
        return 0.0, 0.0