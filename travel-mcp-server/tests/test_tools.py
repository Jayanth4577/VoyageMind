"""Gateway tool tests: live providers via mocked HTTP + demo mode."""
import httpx
import pytest

from travel_mcp.tools import common, maps, transport, weather


def install_mock_http(monkeypatch, handler):
    """Replace the shared client with one that serves canned responses."""
    monkeypatch.setattr(
        common,
        "_client",
        httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0),
    )


OPEN_METEO_BODY = {
    "daily": {
        "time": ["2026-10-01", "2026-10-02"],
        "temperature_2m_max": [30.0, 29.0],
        "temperature_2m_min": [24.0, 23.0],
        "precipitation_sum": [0.0, 8.0],
        "precipitation_probability_max": [10, 90],
        "weather_code": [0, 65],
    },
    "current": {"temperature_2m": 28.5, "precipitation": 0.0, "weather_code": 0},
}


@pytest.mark.anyio
async def test_get_weather_live(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.open-meteo.com" in str(request.url)
        return httpx.Response(200, json=OPEN_METEO_BODY)

    install_mock_http(monkeypatch, handler)
    out = await weather.get_weather(15.3, 74.1, days=2)
    assert out["source"] == "open-meteo"
    assert out["is_mock"] is False
    assert out["daily"][0]["temp_max_c"] == 30.0
    assert out["daily"][1]["significant_rain"] is True  # code 65 + 8mm
    assert "retrieved_at" in out


@pytest.mark.anyio
async def test_get_weather_demo_mode(monkeypatch):
    monkeypatch.setenv("TRAVEL_MCP_DEMO_MODE", "1")
    out = await weather.get_weather(15.3, 74.1, days=3)
    assert out["is_mock"] is True
    assert "DEMO DATA" in out["note"]
    assert len(out["daily"]) == 3


@pytest.mark.anyio
async def test_get_weather_provider_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    install_mock_http(monkeypatch, handler)
    out = await weather.get_weather(15.3, 74.1)
    assert out["status"] == "error"
    assert "weather provider failed" in out["error"]


OSRM_BODY = {
    "code": "Ok",
    "routes": [
        {
            "distance": 50000,
            "duration": 3600,
            "legs": [{"distance": 50000, "duration": 3600}],
        }
    ],
}


@pytest.mark.anyio
async def test_calculate_route_live(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "router.project-osrm.org" in str(request.url)
        return httpx.Response(200, json=OSRM_BODY)

    install_mock_http(monkeypatch, handler)
    pts = [
        {"latitude": 15.5, "longitude": 73.75},
        {"latitude": 15.29, "longitude": 73.96},
    ]
    out = await maps.calculate_route(pts)
    assert out["source"] == "osrm"
    assert out["distance_km"] == 50.0
    assert out["duration_minutes"] == 60
    assert out["legs"][0]["from"] == "point0"


@pytest.mark.anyio
async def test_calculate_route_needs_two_points():
    out = await maps.calculate_route([{"latitude": 1, "longitude": 2}])
    assert out["status"] == "error"


GEOCODE_BODY = {
    "results": [{"name": "Goa", "latitude": 15.3, "longitude": 74.12, "country": "India"}]
}


@pytest.mark.anyio
async def test_geocode_place(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "geocoding-api.open-meteo.com" in str(request.url)
        return httpx.Response(200, json=GEOCODE_BODY)

    install_mock_http(monkeypatch, handler)
    out = await maps.geocode_place("Goa")
    assert out["results"][0]["latitude"] == 15.3
    assert out["source"] == "open-meteo-geocoding"


@pytest.mark.anyio
async def test_nearby_places_rejects_unknown_category():
    out = await maps.find_nearby_places(15.3, 74.1, category="nightclub")
    assert out["status"] == "error"


OVERPASS_BODY = {
    "elements": [
        {"lat": 15.31, "lon": 74.11, "tags": {"name": "Cafe X"}},
        {"lat": 15.29, "lon": 74.10, "tags": {"name": "Cafe Y"}},
    ]
}


@pytest.mark.anyio
async def test_nearby_places_live(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "overpass-api.de" in str(request.url)
        return httpx.Response(200, json=OVERPASS_BODY)

    install_mock_http(monkeypatch, handler)
    out = await maps.find_nearby_places(15.3, 74.1, category="cafe", limit=2)
    names = [r["name"] for r in out["results"]]
    assert names == ["Cafe X", "Cafe Y"]
    assert out["results"][0]["distance_km"] is not None


OSRM_TRIP_BODY = {
    "code": "Ok",
    "trips": [
        {
            "distance": 30000,
            "duration": 2400,
            "legs": [{"duration": 2400}],
            "waypoints": [
                {"waypoint_index": 0},
                {"waypoint_index": 2},
                {"waypoint_index": 1},
            ],
        }
    ],
}


@pytest.mark.anyio
async def test_optimize_route_live(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/trip/v1/driving/" in str(request.url)
        assert "source=first" in str(request.url)
        return httpx.Response(200, json=OSRM_TRIP_BODY)

    install_mock_http(monkeypatch, handler)
    pts = [
        {"latitude": 15.5, "longitude": 73.75},
        {"latitude": 15.29, "longitude": 73.96},
        {"latitude": 15.45, "longitude": 73.8},
    ]
    out = await maps.optimize_route(pts)
    assert out["source"] == "osrm"
    assert out["order"] == [0, 2, 1]  # optimized visiting order
    assert out["duration_minutes"] == 40


@pytest.mark.anyio
async def test_optimize_route_demo_nearest_neighbor(monkeypatch):
    monkeypatch.setenv("TRAVEL_MCP_DEMO_MODE", "1")
    # Point 1 is far north-east; nearest-neighbor from point 0 must pick 2 then 1
    pts = [
        {"latitude": 15.30, "longitude": 74.00},
        {"latitude": 15.60, "longitude": 74.50},
        {"latitude": 15.32, "longitude": 74.02},
    ]
    out = await maps.optimize_route(pts)
    assert out["is_mock"] is True
    assert out["order"][0] == 0
    assert out["order"][1] == 2
    assert out["order"][-1] == 1


@pytest.mark.anyio
async def test_optimize_route_failure_is_structured(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    install_mock_http(monkeypatch, handler)
    out = await maps.optimize_route(
        [{"latitude": 1, "longitude": 2}, {"latitude": 3, "longitude": 4}]
    )
    assert out["status"] == "error"


FX_BODY = {"rates": {"INR": 83.5, "EUR": 0.92}}


@pytest.mark.anyio
async def test_exchange_rate(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "open.er-api.com" in str(request.url)
        return httpx.Response(200, json=FX_BODY)

    install_mock_http(monkeypatch, handler)
    out = await transport.get_exchange_rate("USD", "INR")
    assert out["rate"] == 83.5
    assert out["is_mock"] is False


@pytest.mark.anyio
async def test_exchange_rate_unknown_currency(monkeypatch):
    install_mock_http(monkeypatch, lambda request: httpx.Response(200, json=FX_BODY))
    out = await transport.get_exchange_rate("USD", "XYZ")
    assert out["status"] == "error"


@pytest.mark.anyio
async def test_search_transport_without_key_is_labeled_mock(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    out = await transport.search_transport("BLR", "GOI", "2026-10-01")
    assert out["is_mock"] is True
    assert "DEMO DATA" in out["note"]
    assert len(out["offers"]) == 3


@pytest.mark.anyio
async def test_search_transport_serpapi(monkeypatch):
    serp_response = {
        "best_flights": [
            {
                "flights": [
                    {
                        "airline": "Air India",
                        "flight_number": "AI 101",
                        "departure_airport": {"time": "2026-10-01 10:00"},
                        "arrival_airport": {"time": "2026-10-01 11:30"},
                        "duration": 90,
                    }
                ],
                "total_duration": 90,
                "price": 5000,
            }
        ]
    }
    install_mock_http(monkeypatch, lambda request: httpx.Response(200, json=serp_response))
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    out = await transport.search_transport("BLR", "GOI", "2026-10-01")
    assert out["is_mock"] is False
    assert out["source"] == "serpapi"
    assert len(out["offers"]) == 1
    assert out["offers"][0]["airline"] == "Air India (AI 101)"
    assert out["offers"][0]["price"] == 5000.0


@pytest.mark.anyio
async def test_web_search_without_provider_refuses(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    out = await transport.web_search("festivals in Goa October")
    assert out["status"] == "no_provider"
    assert out["results"] == []


@pytest.mark.anyio
async def test_demo_mode_transport(monkeypatch):
    monkeypatch.setenv("TRAVEL_MCP_DEMO_MODE", "1")
    out = await transport.search_transport("BLR", "GOI", "2026-10-01")
    assert out["is_mock"] is True
    assert out["offers"][0]["price"] > 0


SERPAPI_FLIGHTS_BODY = {
    "search_metadata": {"id": "x"},
    "best_flights": [
        {
            "price": 5210,
            "total_duration": 95,
            "flights": [
                {
                    "airline": "IndiGo",
                    "flight_number": "6E-123",
                    "duration": 95,
                    "departure_airport": {"name": "Pune", "id": "PNQ", "time": "2026-12-05 07:30"},
                    "arrival_airport": {"name": "Goa", "id": "GOI", "time": "2026-12-05 09:05"},
                }
            ],
        }
    ],
    "other_flights": [],
}

SERPAPI_HOTELS_BODY = {
    "properties": [
        {
            "property_id": "p1",
            "name": "Brightland Resort",
            "type": "hotel",
            "rate_per_night": {"lowest": 6400},
            "overall_rating": 4.4,
        },
        {
            "property_id": "p2",
            "name": "Valley View Inn",
            "type": "guest_house",
            "rate_per_night": {"lowest": 2100},
            "overall_rating": 4.1,
        },
    ]
}


@pytest.mark.anyio
async def test_serpapi_flights_parse(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "engine=google_flights" in str(request.url)
        assert "adults=3" in str(request.url)
        assert "currency=INR" in str(request.url)
        return httpx.Response(200, json=SERPAPI_FLIGHTS_BODY)

    install_mock_http(monkeypatch, handler)
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.delenv("TRAVEL_MCP_DEMO_MODE", raising=False)

    out = await transport.search_transport("Pune", "GOA", "2026-12-05", adults=3)
    assert out["source"] == "serpapi"
    assert out["is_mock"] is False
    offer = out["offers"][0]
    assert "IndiGo" in offer["airline"]
    assert offer["price"] == 5210
    assert offer["currency"] == "INR"
    assert offer["duration_minutes"] == 95


@pytest.mark.anyio
async def test_serpapi_hotels_parse(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "engine=google_hotels" in str(request.url)
        assert "adults=2" in str(request.url)
        return httpx.Response(200, json=SERPAPI_HOTELS_BODY)

    install_mock_http(monkeypatch, handler)
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.delenv("TRAVEL_MCP_DEMO_MODE", raising=False)

    out = await transport.search_stays("Mahabaleshwar", "2026-12-05", "2026-12-07", guests=2)
    assert out["source"] == "serpapi"
    assert out["stays"][0]["name"] == "Brightland Resort"
    assert out["stays"][0]["price_per_night"] == 6400


@pytest.mark.anyio
async def test_serpapi_flight_error_falls_back_to_demo(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "serpapi.com" in str(request.url):
            return httpx.Response(500, text="boom")
        raise AssertionError("unexpected call")

    install_mock_http(monkeypatch, handler)
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.delenv("TRAVEL_MCP_DEMO_MODE", raising=False)

    out = await transport.search_transport("BLR", "GOI", "2026-12-01")
    assert out["is_mock"] is True  # honest labeled fallback


def test_city_to_iata_mapping():
    assert transport._to_iata("Hyderabad") == "HYD"
    assert transport._to_iata("pune") == "PNQ"
    assert transport._to_iata("BLR") == "BLR"  # already a code
    assert transport._to_iata("nowhere") == "NOWHERE"  # passthrough
