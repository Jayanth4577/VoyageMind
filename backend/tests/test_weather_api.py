"""Weather endpoint: geocode write-back + graceful failures (spec §24/§31)."""
import uuid


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers, **extra):
    payload = {
        "destination_name": "Goa",
        "start_date": "2026-10-01",
        "end_date": "2026-10-03",
    }
    payload.update(extra)
    return client.post("/trips", json=payload, headers=headers).json()


def patch_facade(monkeypatch, geo, wx):
    from app.mcp import travel_mcp as tm

    async def fake_geo(name):
        return geo

    async def fake_wx(latitude, longitude, days=5):
        return wx

    monkeypatch.setattr(tm.travel_mcp.maps, "geocode_place", fake_geo)
    monkeypatch.setattr(tm.travel_mcp.weather, "get_weather", fake_wx)


def test_weather_with_preset_coordinates(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(
        client, headers, destination_lat=15.3, destination_lng=74.1
    )
    patch_facade(
        monkeypatch,
        geo={"source": "test", "results": []},
        wx={
            "source": "open-meteo",
            "is_mock": False,
            "retrieved_at": "2026-09-08T00:00:00+00:00",
            "daily": [{"date": "2026-10-01", "rain_probability": 20}],
        },
    )
    res = client.get(f"/trips/{trip['id']}/weather", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "open-meteo"
    assert body["daily"][0]["rain_probability"] == 20
    assert body["resolved_destination"]["latitude"] == 15.3


def test_weather_geocodes_and_writes_back(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)  # no coordinates
    patch_facade(
        monkeypatch,
        geo={
            "source": "test",
            "results": [{"name": "Goa", "latitude": 15.29, "longitude": 74.12}],
        },
        wx={"source": "mock", "is_mock": True, "daily": []},
    )
    res = client.get(f"/trips/{trip['id']}/weather", headers=headers)
    assert res.status_code == 200

    detail = client.get(f"/trips/{trip['id']}", headers=headers).json()
    assert detail["destination_lat"] == 15.29  # persisted for future calls
    assert detail["destination_lng"] == 74.12


def test_weather_unresolvable_destination_422(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    patch_facade(monkeypatch, geo={"source": "test", "results": []}, wx={})
    res = client.get(f"/trips/{trip['id']}/weather", headers=headers)
    assert res.status_code == 422


def test_weather_requires_owner(client, monkeypatch):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    trip = make_trip(client, headers_a, destination_lat=1.0, destination_lng=2.0)
    patch_facade(monkeypatch, geo={"results": []}, wx={})
    res = client.get(f"/trips/{trip['id']}/weather", headers=headers_b)
    assert res.status_code == 404
