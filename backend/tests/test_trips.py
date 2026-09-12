import uuid

import pytest


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def trip_payload(**overrides):
    payload = {
        "origin_name": "Bengaluru",
        "destination_name": "Goa",
        "start_date": "2026-10-01",
        "end_date": "2026-10-05",
        "num_travelers": 4,
        "total_budget": 50000,
        "currency": "INR",
        "trip_style": "relaxed",
        "preferences": {"interests": ["beaches", "food", "nightlife", "culture"]},
    }
    payload.update(overrides)
    return payload


def create_trip(client, headers, **overrides):
    return client.post("/trips", json=trip_payload(**overrides), headers=headers)


def test_create_trip_creates_daily_rows(client):
    headers = auth_headers(client)
    res = create_trip(client, headers)
    assert res.status_code == 201
    body = res.json()
    assert body["destination_name"] == "Goa"
    assert len(body["days"]) == 5  # Oct 1-5
    assert [d["day_number"] for d in body["days"]] == [1, 2, 3, 4, 5]


def test_trips_require_auth(client):
    assert client.get("/trips").status_code == 401
    assert client.post("/trips", json=trip_payload()).status_code == 401


def test_list_and_detail_owned_only(client):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    created = create_trip(client, headers_a).json()

    listed = client.get("/trips", headers=headers_a).json()["items"]
    assert [t["id"] for t in listed] == [created["id"]]
    assert client.get("/trips", headers=headers_b).json()["items"] == []

    assert client.get(f"/trips/{created['id']}", headers=headers_a).status_code == 200
    # Other users must not see the trip (404, not 403 — avoid existence leak)
    assert client.get(f"/trips/{created['id']}", headers=headers_b).status_code == 404


def test_update_extends_dates_and_syncs_days(client):
    headers = auth_headers(client)
    created = create_trip(client, headers).json()
    res = client.put(
        f"/trips/{created['id']}",
        json={"end_date": "2026-10-07", "total_budget": 60000},
        headers=headers,
    )
    assert res.status_code == 200
    assert len(res.json()["days"]) == 7


def test_delete_trip(client):
    headers = auth_headers(client)
    created = create_trip(client, headers).json()
    assert client.delete(f"/trips/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/trips/{created['id']}", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"end_date": "2026-09-30"},  # end before start
        {"num_travelers": 0},
        {"total_budget": -5},
        {"currency": "RUPEE!!!"},
    ],
)
def test_invalid_inputs_422(client, overrides):
    headers = auth_headers(client)
    assert create_trip(client, headers, **overrides).status_code == 422
