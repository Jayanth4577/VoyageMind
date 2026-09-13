"""Analytics endpoint tests — deterministic aggregates."""
import uuid


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers, budget=None, dest="Goa"):
    return client.post(
        "/trips",
        json={
            "destination_name": dest,
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "total_budget": budget,
            "currency": "INR",
        },
        headers=headers,
    ).json()


def test_summary_aggregates_trips(client):
    headers = auth_headers(client)
    trip_a = make_trip(client, headers, budget=10000)
    trip_b = make_trip(client, headers, budget=20000, dest="Manali")

    client.post(
        f"/trips/{trip_a['id']}/budget",
        json={"category": "food", "label": "Dinner", "amount": 2000},
        headers=headers,
    )
    client.post(
        f"/trips/{trip_b['id']}/budget",
        json={"category": "transport", "label": "Bus", "amount": 3000},
        headers=headers,
    )
    client.post(
        f"/trips/{trip_b['id']}/budget",
        json={"category": "food", "label": "Cafe", "amount": 1000},
        headers=headers,
    )

    res = client.get("/analytics/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["trip_count"] == 2

    inr = body["totals_by_currency"]["INR"]
    assert inr["total_spent"] == 6000
    assert inr["total_budget"] == 30000
    assert inr["by_category"]["food"] == 3000
    assert inr["by_category"]["transport"] == 3000

    by_id = {t["trip_id"]: t for t in body["trips"]}
    assert by_id[trip_a["id"]]["spent"] == 2000
    assert by_id[trip_a["id"]]["state"] == "under"
    assert by_id[trip_b["id"]]["by_category"] == {"transport": 3000.0, "food": 1000.0}


def test_summary_upcoming_and_empty(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    res = client.get("/analytics/summary", headers=headers)
    body = res.json()
    assert body["trip_count"] == 1
    assert body["upcoming"]["trip_id"] == trip["id"]

    # Another user sees nothing
    other = auth_headers(client)
    empty = client.get("/analytics/summary", headers=other)
    assert empty.json()["trip_count"] == 0
    assert empty.json()["upcoming"] is None
