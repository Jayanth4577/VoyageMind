"""Itinerary + budget API integration tests (spec §24 endpoints)."""
import uuid


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers):
    res = client.post(
        "/trips",
        json={
            "destination_name": "Goa",
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "num_travelers": 2,
            "total_budget": 50000,
            "currency": "INR",
        },
        headers=headers,
    )
    return res.json()


def add_activity(client, headers, trip, day, **overrides):
    payload = {
        "day_id": day["id"],
        "name": "Baga Beach",
        "category": "BEACH",
        "start_time": "10:00",
        "end_time": "12:00",
        "estimated_cost": 0,
        "weather_sensitive": True,
    }
    payload.update(overrides)
    return client.post(
        f"/trips/{trip['id']}/activities", json=payload, headers=headers
    )


def test_add_activity_and_derive_end_time(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day = trip["days"][0]

    res = add_activity(client, headers, trip, day)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Baga Beach"
    assert body["source"] == "user"
    assert body["user_selected"] is True

    # duration-only activity derives end_time
    res2 = add_activity(
        client,
        headers,
        trip,
        day,
        name="Lunch",
        category="RESTAURANT",
        start_time="13:00",
        end_time="",
        duration_minutes=60,
        estimated_cost=800,
    )
    assert res2.status_code == 201
    assert res2.json()["end_time"] == "14:00"


def test_activity_cost_flows_into_budget(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day = trip["days"][0]

    created = add_activity(
        client, headers, trip, day, name="Dinner", category="RESTAURANT",
        estimated_cost=1200,
    ).json()
    budget = client.get(f"/trips/{trip['id']}/budget", headers=headers).json()
    assert budget["spent"] == 1200
    assert budget["by_category"]["food"] == 1200
    assert budget["state"] == "under"

    # updating cost updates the mirrored budget line
    client.put(
        f"/activities/{created['id']}", json={"estimated_cost": 1500}, headers=headers
    )
    budget = client.get(f"/trips/{trip['id']}/budget", headers=headers).json()
    assert budget["spent"] == 1500

    # deleting the activity removes the line
    client.delete(f"/activities/{created['id']}", headers=headers)
    budget = client.get(f"/trips/{trip['id']}/budget", headers=headers).json()
    assert budget["spent"] == 0


def test_activity_category_maps_to_budget_category(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day = trip["days"][0]

    add_activity(client, headers, trip, day, name="Taxi", category="TRANSPORT",
                 estimated_cost=300)
    add_activity(client, headers, trip, day, name="Museum", category="MUSEUM",
                 estimated_cost=200)
    budget = client.get(f"/trips/{trip['id']}/budget", headers=headers).json()
    assert budget["by_category"] == {"activities": 200.0, "local_transport": 300.0}


def test_move_activity_between_days(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day1, day2 = trip["days"][0], trip["days"][1]
    created = add_activity(client, headers, trip, day1).json()

    moved = client.post(
        f"/activities/{created['id']}/move",
        json={"target_day_id": day2["id"], "start_time": "15:00", "end_time": "17:00"},
        headers=headers,
    )
    assert moved.status_code == 200
    assert moved.json()["day_id"] == day2["id"]
    assert moved.json()["start_time"] == "15:00"

    itinerary = client.get(f"/trips/{trip['id']}/itinerary", headers=headers).json()
    assert len(itinerary["days"][0]["activities"]) == 0
    assert len(itinerary["days"][1]["activities"]) == 1


def test_reorder_day(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day = trip["days"][0]
    a = add_activity(client, headers, trip, day, name="A").json()
    b = add_activity(client, headers, trip, day, name="B").json()
    c = add_activity(client, headers, trip, day, name="C").json()

    res = client.post(
        f"/trips/{trip['id']}/days/{day['id']}/reorder",
        json={"activity_ids": [c["id"], a["id"], b["id"]]},
        headers=headers,
    )
    assert res.status_code == 200
    names = [act["name"] for act in res.json()["activities"]]
    assert names == ["C", "A", "B"]

    # mismatched set rejected wholesale
    bad = client.post(
        f"/trips/{trip['id']}/days/{day['id']}/reorder",
        json={"activity_ids": [a["id"], b["id"]]},
        headers=headers,
    )
    assert bad.status_code == 422


def test_check_conflicts_endpoint(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day = trip["days"][0]
    add_activity(client, headers, trip, day, name="A", start_time="10:00", end_time="12:00")
    add_activity(client, headers, trip, day, name="B", start_time="11:00", end_time="12:30")

    report = client.post(f"/trips/{trip['id']}/check-conflicts", headers=headers).json()
    assert report["has_conflicts"] is True
    assert report["issues"][0]["kind"] == "overlap"


def test_budget_manual_items_and_currency_guard(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)

    ok = client.post(
        f"/trips/{trip['id']}/budget",
        json={"category": "transport", "label": "Flights", "amount": 16000},
        headers=headers,
    )
    assert ok.status_code == 201

    wrong_currency = client.post(
        f"/trips/{trip['id']}/budget",
        json={"category": "food", "amount": 10, "currency": "USD"},
        headers=headers,
    )
    assert wrong_currency.status_code == 422

    summary = client.get(f"/trips/{trip['id']}/budget", headers=headers).json()
    assert summary["spent"] == 16000
    assert summary["remaining"] == 34000


def test_cross_user_access_denied(client):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    trip = make_trip(client, headers_a)
    day = trip["days"][0]
    created = add_activity(client, headers_a, trip, day).json()

    assert (
        client.put(
            f"/activities/{created['id']}", json={"name": "Hijack"}, headers=headers_b
        ).status_code
        == 404
    )
    assert (
        client.get(f"/trips/{trip['id']}/budget", headers=headers_b).status_code == 404
    )


def test_invalid_activity_times_422(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    day = trip["days"][0]
    res = add_activity(client, headers, trip, day, start_time="25:00")
    assert res.status_code == 422
