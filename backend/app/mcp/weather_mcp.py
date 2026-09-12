"""Weather facade: Redis cache (30 min) -> MCP gateway -> labeled mock."""

from app.core import redis_client
from app.mcp import mock_fallbacks
from app.mcp.client import TravelMCPClient

TTL_WEATHER = 1800


def _usable(payload: dict) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("status") is None
        and payload.get("source") is not None
    )


class WeatherMCP:
    def __init__(self, client: TravelMCPClient | None = None) -> None:
        self._client = client

    def client(self) -> TravelMCPClient:
        return self._client or TravelMCPClient()

    async def get_weather(self, latitude: float, longitude: float, days: int = 5) -> dict:
        key = f"wx:{latitude:.3f}:{longitude:.3f}:{days}"
        cached = await redis_client.cache_get_json(key)
        if cached is not None:
            return {**cached, "cached": True}

        live = await self.client().call_tool(
            "get_weather", {"latitude": latitude, "longitude": longitude, "days": days}
        )
        if _usable(live):
            if not live.get("is_mock"):
                await redis_client.cache_set_json(key, live, TTL_WEATHER)
            return live
        return mock_fallbacks.mock_weather(latitude, longitude, days)
