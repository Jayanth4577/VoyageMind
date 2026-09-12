"""Maps facade: geocoding, routing, optimization, places — cached with long TTLs."""

from app.core import redis_client
from app.mcp import mock_fallbacks
from app.mcp.client import TravelMCPClient
from app.mcp.weather_mcp import _usable
from app.utils.geo_utils import haversine_km

TTL_GEOCODE = 7 * 24 * 3600
TTL_ROUTE = 24 * 3600
TTL_PLACES = 24 * 3600
TTL_NEARBY = 6 * 3600

_HEURISTIC_SPEED_KMH = 40.0


class MapsMCP:
    def __init__(self, client: TravelMCPClient | None = None) -> None:
        self._client = client

    def client(self) -> TravelMCPClient:
        return self._client or TravelMCPClient()

    async def geocode_place(self, name: str) -> dict:
        key = f"geo:{name.lower().strip()}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool("geocode_place", {"name": name})
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_GEOCODE)
            return live
        return mock_fallbacks.mock_geocode(name)

    async def calculate_route(self, points: list[dict]) -> dict:
        coord_key = ";".join(f"{p['latitude']:.4f},{p['longitude']:.4f}" for p in points)
        key = f"route:{coord_key}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool("calculate_route", {"points": points})
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_ROUTE)
            return live
        return mock_fallbacks.mock_route(points)

    async def optimize_route(self, points: list[dict]) -> dict:
        """Recommended visiting order. Falls back to a labeled nearest-neighbor heuristic."""
        coord_key = ";".join(f"{p['latitude']:.4f},{p['longitude']:.4f}" for p in points)
        key = f"optroute:{coord_key}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool("optimize_route", {"points": points})
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_ROUTE)
            return live
        return self._nearest_neighbor(points)

    @staticmethod
    def _nearest_neighbor(points: list[dict]) -> dict:
        """Local deterministic ordering. Distances are real; durations assume 40 km/h."""
        order = [0]
        remaining = list(range(1, len(points)))
        current = 0
        while remaining:
            nxt = min(
                remaining,
                key=lambda j: haversine_km(
                    points[current]["latitude"],
                    points[current]["longitude"],
                    points[j]["latitude"],
                    points[j]["longitude"],
                ),
            )
            order.append(nxt)
            remaining.remove(nxt)
            current = nxt
        total_km = sum(
            haversine_km(
                points[a]["latitude"],
                points[a]["longitude"],
                points[b]["latitude"],
                points[b]["longitude"],
            )
            for a, b in zip(order, order[1:], strict=False)
        )
        return {
            "source": "heuristic-nearest-neighbor",
            "is_mock": True,
            "retrieved_at": None,
            "note": (
                "HEURISTIC — real straight-line distances, durations assumed at "
                f"{_HEURISTIC_SPEED_KMH:.0f} km/h (routing service unavailable)"
            ),
            "order": order,
            "distance_km": round(total_km, 1),
            "duration_minutes": round(total_km / _HEURISTIC_SPEED_KMH * 60),
        }

    async def search_places(self, query: str, count: int = 5) -> dict:
        key = f"places:{query.lower().strip()}:{count}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool("search_places", {"query": query, "count": count})
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_PLACES)
            return live
        return {
            **mock_fallbacks.mock_nearby(15.2993, 74.124, "attraction", count),
            "note": "DEMO DATA — synthetic place search results",
            "query": query,
        }

    async def find_nearby_places(
        self, latitude: float, longitude: float, category: str = "restaurant", radius_m: int = 2000
    ) -> dict:
        key = f"nearby:{latitude:.3f}:{longitude:.3f}:{category}:{radius_m}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool(
            "find_nearby_places",
            {
                "latitude": latitude,
                "longitude": longitude,
                "category": category,
                "radius_m": radius_m,
            },
        )
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_NEARBY)
            return live
        return mock_fallbacks.mock_nearby(latitude, longitude, category)
