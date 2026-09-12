"""Transport/stays/FX/web-search facade: short TTLs for volatile prices."""

from app.core import redis_client
from app.mcp import mock_fallbacks
from app.mcp.client import TravelMCPClient
from app.mcp.weather_mcp import _usable

TTL_TRANSPORT = 15 * 60
TTL_STAYS = 6 * 3600
TTL_FX = 24 * 3600


class FlightMCP:
    def __init__(self, client: TravelMCPClient | None = None) -> None:
        self._client = client

    def client(self) -> TravelMCPClient:
        return self._client or TravelMCPClient()

    async def search_transport(self, origin: str, destination: str, date: str) -> dict:
        key = f"transport:{origin.upper()}:{destination.upper()}:{date}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool(
            "search_transport",
            {"origin": origin, "destination": destination, "date": date},
        )
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_TRANSPORT)
            return live
        return mock_fallbacks.mock_transport(origin, destination, date)

    async def search_stays(
        self, location: str, check_in: str, check_out: str, guests: int = 2
    ) -> dict:
        key = f"stays:{location.lower().strip()}:{check_in}:{check_out}:{guests}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool(
            "search_stays",
            {"location": location, "check_in": check_in, "check_out": check_out, "guests": guests},
        )
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_STAYS)
            return live
        return mock_fallbacks.mock_stays(location, check_in, check_out, guests)

    async def get_exchange_rate(self, base: str, target: str) -> dict:
        key = f"fx:{base.upper()}:{target.upper()}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}
        live = await self.client().call_tool("get_exchange_rate", {"base": base, "target": target})
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_FX)
            return live
        # FX is arithmetic-adjacent and must never be silently invented;
        # surface the failure instead of a fake rate.
        return {"status": "unavailable", "note": "Exchange rate unavailable", "is_mock": True}

    async def web_search(self, query: str) -> dict:
        # Volatile by nature; never cached.
        live = await self.client().call_tool("web_search", {"query": query})
        if _usable(live):
            return live
        return {
            "status": "unavailable",
            "note": "Web search unavailable; no results fabricated",
            "query": query,
            "results": [],
            "is_mock": True,
        }
