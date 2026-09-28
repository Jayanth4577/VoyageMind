"""Postgres-backed endpoint tests: geocoding + budget item management."""
import uuid
from unittest.mock import AsyncMock


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers, **extra):
    payload = {"destination_name": "Goa", "start_date": "2026-10-01", "end_date": "2026-10-02"}
    payload.update(extra)
    return client.post("/trips", json=payload, headers=headers).json()


def test_geocode_resolves_and_persists(client, monkeypatch):
    from app.mcp import travel_mcp as tm

    headers = auth_headers(client)
    trip = make_trip(client, headers)  # no coordinates yet

    async def fake_geo(name):
        return {
            "source": "test",
            "results": [{"name": name, "latitude": 17.92, "longitude": 73.67}],
        }

    monkeypatch.setattr(tm.travel_mcp.maps, "geocode_place", AsyncMock(side_effect=fake_geo))

    res = client.get(f"/trips/{trip['id']}/geocode", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["latitude"] == 17.92
    assert body["longitude"] == 73.67

    # persisted on the trip
    detail = client.get(f"/trips/{trip['id']}", headers=headers).json()
    assert detail["destination_lat"] == 17.92


def test_geocode_unresolvable_422(client, monkeypatch):
    from app.mcp import travel_mcp as tm

    headers = auth_headers(client)
    trip = make_trip(client, headers)
    monkeypatch.setattr(
        tm.travel_mcp.maps,
        "geocode_place",
        AsyncMock(return_value={"source": "test", "results": []}),
    )
    assert client.get(f"/trips/{trip['id']}/geocode", headers=headers).status_code == 422


def test_budget_items_list_and_delete(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)

    created = client.post(
        f"/trips/{trip['id']}/budget",
        json={"category": "food", "label": "Dinner", "amount": 500},
        headers=headers,
    ).json()

    items = client.get(f"/trips/{trip['id']}/budget/items", headers=headers).json()
    assert [i["id"] for i in items] == [created["id"]]
    assert items[0]["source_ref"] == "manual"

    assert (
        client.delete(f"/budget-items/{created['id']}", headers=headers).status_code == 204
    )
    assert client.get(f"/trips/{trip['id']}/budget/items", headers=headers).json() == []


def test_budget_items_ownership(client):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    trip = make_trip(client, headers_a)
    res = client.get(f"/trips/{trip['id']}/budget/items", headers=headers_b)
    assert res.status_code == 404
