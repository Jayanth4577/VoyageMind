"""Group preferences API tests (spec §20)."""
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
        },
        headers=headers,
    )
    return res.json()


def test_preferences_roundtrip(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)

    res = client.put(
        f"/trips/{trip['id']}/preferences",
        json={
            "people": [
                {"person_name": "A", "preferences": {"beach": 1.0, "food": 0.8}},
                {"person_name": "B", "preferences": {"beach": 0.8}},
            ]
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["saved"] == 2

    listing = client.get(f"/trips/{trip['id']}/preferences", headers=headers).json()
    assert len(listing) == 2

    analysis = client.get(
        f"/trips/{trip['id']}/preferences/analysis", headers=headers
    ).json()
    assert analysis["travelers"] == 2
    assert analysis["interests"]["beach"]["average"] == 0.9


def test_invalid_scores_rejected(client):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    res = client.put(
        f"/trips/{trip['id']}/preferences",
        json={"people": [{"person_name": "A", "preferences": {"beach": "lots"}}]},
        headers=headers,
    )
    assert res.status_code == 422


def test_ownership_enforced(client):
    headers_a = auth_headers(client)
    headers_b = auth_headers(client)
    trip = make_trip(client, headers_a)
    res = client.put(
        f"/trips/{trip['id']}/preferences",
        json={"people": [{"person_name": "X", "preferences": {}}]},
        headers=headers_b,
    )
    assert res.status_code == 404


def test_generate_includes_group_analysis(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    client.put(
        f"/trips/{trip['id']}/preferences",
        json={"people": [{"person_name": "A", "preferences": {"beach": 1.0}}]},
        headers=headers,
    )

    from app.agents.context import AgentResult
    from app.api import agents as agents_api

    captured = {}

    class FakeMaster:
        def __init__(self, llm=None):
            pass

        async def run(self, context):
            captured["trip_data"] = context.trip_data
            return AgentResult(
                agent_name="MasterAgent", status="partial", data={}, tool_calls=[]
            )

    monkeypatch.setattr(agents_api, "MasterAgent", FakeMaster)

    res = client.post(f"/trips/{trip['id']}/generate", headers=headers)
    assert res.status_code == 200
    gp = captured["trip_data"].get("group_preferences")
    assert gp is not None
    assert gp["travelers"] == 1
    assert gp["balanced_weights"]["beach"] == 1.0
