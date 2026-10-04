"""Discovery endpoints: nearby destinations, transport, stays (mock facades)."""
import uuid
from unittest.mock import AsyncMock


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers, origin="Pune"):
    return client.post(
        "/trips",
        json={
            "origin_name": origin,
            "destination_name": "Mahabaleshwar",
            "start_date": "2026-12-05",
            "end_date": "2026-12-07",
            "num_travelers": 2,
        },
        headers=headers,
    ).json()


def patch_maps(monkeypatch, dests):
    async def fake_dests(latitude, longitude, exclude="", radius_km=40):
        return {"source": "overpass", "is_mock": False, "results": dests}

    monkeypatch.setattr(
        tm_travel_mcp().maps, "find_nearby_destinations", AsyncMock(side_effect=fake_dests)
    )


def tm_travel_mcp():
    from app.mcp import travel_mcp as tm

    return tm.travel_mcp


def test_nearby_destinations_excludes_destination(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    patch_maps(
        monkeypatch,
        [
            {
                "name": "Panchgani",
                "place_type": "town",
                "latitude": 17.92,
                "longitude": 73.8,
                "distance_km": 19.5,
                "population": 15000,
                "maps_url": "https://www.openstreetmap.org/x",
            },
            {
                "name": "Mahabaleshwar",
                "place_type": "town",
                "latitude": 17.92,
                "longitude": 73.66,
                "distance_km": 0.2,
                "population": 12000,
                "maps_url": "x",
            },
        ],
    )
    res = client.get(f"/trips/{trip['id']}/nearby-destinations", headers=headers)
    assert res.status_code == 200
    body = res.json()
    names = [r["name"] for r in body["results"]]
    assert "Panchgani" in names
    assert "Mahabaleshwar" not in names  # destination excluded
    assert body["results"][0]["maps_url"].startswith("https://www.openstreetmap.org/")


def test_transport_options_passes_trip_context(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)

    async def fake_transport(origin, destination, date):
        assert origin == "Pune"
        assert destination == "Mahabaleshwar"
        assert date == "2026-12-05"
        return {
            "source": "mock",
            "is_mock": True,
            "offers": [
                {
                    "id": "o1",
                    "airline": "DemoAir",
                    "departure_at": "2026-12-05T07:30:00",
                    "arrival_at": "2026-12-05T09:00:00",
                    "duration_minutes": 90,
                    "price": 3500,
                    "currency": "INR",
                }
            ],
        }

    tm_travel_mcp().flights.search_transport = AsyncMock(side_effect=fake_transport)
    res = client.get(f"/trips/{trip['id']}/transport-options", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["offers"][0]["airline"] == "DemoAir"
    assert body["query"]["date"] == "2026-12-05"


def test_transport_requires_origin(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers, origin="")
    res = client.get(f"/trips/{trip['id']}/transport-options", headers=headers)
    assert res.status_code == 422


def test_stays_uses_trip_dates_and_guests(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)

    async def fake_stays(location, check_in, check_out, guests=2):
        assert location == "Mahabaleshwar"
        assert check_in == "2026-12-05" and check_out == "2026-12-07"
        assert guests == 2
        return {
            "source": "mock",
            "is_mock": True,
            "stays": [
                {
                    "id": "s1",
                    "name": "Demo Resort",
                    "location_name": location,
                    "price_per_night": 2500,
                    "rating": 8.1,
                }
            ],
        }

    tm_travel_mcp().flights.search_stays = AsyncMock(side_effect=fake_stays)
    res = client.get(f"/trips/{trip['id']}/stays", headers=headers)
    assert res.status_code == 200
    assert res.json()["stays"][0]["name"] == "Demo Resort"


def test_discover_ownership(client):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    trip = make_trip(client, headers_a)
    for path in ("nearby-destinations", "transport-options", "stays"):
        res = client.get(f"/trips/{trip['id']}/{path}", headers=headers_b)
        assert res.status_code == 404, path
