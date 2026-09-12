"""Facade tests: cache behavior + fallback to labeled mocks (spec §25/§26/§3.10)."""
import pytest

from app.core import redis_client
from app.mcp.flight_mcp import FlightMCP
from app.mcp.maps_mcp import MapsMCP
from app.mcp.weather_mcp import WeatherMCP

LIVE_WEATHER = {
    "source": "open-meteo",
    "retrieved_at": "2026-09-08T00:00:00+00:00",
    "is_mock": False,
    "daily": [{"date": "2026-10-01", "significant_rain": False}],
}
GATEWAY_MOCK = {
    "source": "mock",
    "retrieved_at": "2026-09-08T00:00:00+00:00",
    "is_mock": True,
    "note": "DEMO DATA",
    "daily": [],
}


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return self.responses[name]


@pytest.fixture()
def mem_cache(monkeypatch):
    store = {}

    async def cache_get(key):
        return store.get(key)

    async def cache_set(key, value, ttl_seconds):
        store[key] = value

    monkeypatch.setattr(redis_client, "cache_get_json", cache_get)
    monkeypatch.setattr(redis_client, "cache_set_json", cache_set)
    return store


@pytest.mark.anyio
async def test_weather_live_is_cached(mem_cache):
    fake = FakeClient({"get_weather": dict(LIVE_WEATHER)})
    facade = WeatherMCP(client=fake)

    first = await facade.get_weather(15.3, 74.1, days=3)
    assert first["source"] == "open-meteo"
    assert "cached" not in first or first.get("cached") is not True

    second = await facade.get_weather(15.3, 74.1, days=3)
    assert second["cached"] is True
    assert len(fake.calls) == 1  # second call served from cache


@pytest.mark.anyio
async def test_weather_error_falls_back_to_labeled_mock(mem_cache):
    fake = FakeClient({"get_weather": {"status": "unavailable", "error": "down"}})
    facade = WeatherMCP(client=fake)

    out = await facade.get_weather(15.3, 74.1, days=3)
    assert out["is_mock"] is True
    assert "DEMO DATA" in out["note"]
    assert len(out["daily"]) == 3
    assert mem_cache == {}  # mocks must not be cached


@pytest.mark.anyio
async def test_weather_gateway_demo_mock_passes_through_uncached(mem_cache):
    fake = FakeClient({"get_weather": dict(GATEWAY_MOCK)})
    facade = WeatherMCP(client=fake)

    out = await facade.get_weather(15.3, 74.1, days=2)
    assert out["is_mock"] is True
    assert mem_cache == {}


@pytest.mark.anyio
async def test_route_live_and_fallback(mem_cache):
    pts = [
        {"latitude": 15.5, "longitude": 73.75},
        {"latitude": 15.29, "longitude": 73.96},
    ]
    live = {
        "source": "osrm",
        "is_mock": False,
        "retrieved_at": "2026-09-08T00:00:00+00:00",
        "distance_km": 42.0,
        "duration_minutes": 55,
        "legs": [],
    }
    facade = MapsMCP(client=FakeClient({"calculate_route": dict(live)}))
    out = await facade.calculate_route(pts)
    assert out["distance_km"] == 42.0

    mem_cache.clear()  # drop the cached live result so the next call must hit its client

    failing = MapsMCP(
        client=FakeClient({"calculate_route": {"status": "error", "error": "x"}})
    )
    out2 = await failing.calculate_route(pts)
    assert out2["is_mock"] is True
    assert out2["distance_km"] > 0


@pytest.mark.anyio
async def test_geocode_fallback(mem_cache):
    facade = MapsMCP(client=FakeClient({"geocode_place": {"status": "unavailable"}}))
    out = await facade.geocode_place("Goa")
    assert out["is_mock"] is True
    assert out["results"][0]["latitude"] == pytest.approx(15.2993)


@pytest.mark.anyio
async def test_transport_fallback_labeled(mem_cache):
    facade = FlightMCP(client=FakeClient({"search_transport": {"status": "error"}}))
    out = await facade.search_transport("BLR", "GOI", "2026-10-01")
    assert out["is_mock"] is True
    assert out["offers"]


@pytest.mark.anyio
async def test_exchange_rate_never_fabricated(mem_cache):
    facade = FlightMCP(client=FakeClient({"get_exchange_rate": {"status": "error"}}))
    out = await facade.get_exchange_rate("USD", "INR")
    assert out["status"] == "unavailable"
    assert "rate" not in out


@pytest.mark.anyio
async def test_web_search_never_fabricated(mem_cache):
    facade = FlightMCP(client=FakeClient({"web_search": {"status": "unavailable"}}))
    out = await facade.web_search("festivals Goa")
    assert out["status"] == "unavailable"
    assert out["results"] == []
