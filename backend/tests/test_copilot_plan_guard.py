"""Golden-rule guard: the copilot never silently adds onto a user-built trip."""
import uuid

from app.agents.context import AgentResult


def auth_headers(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_trip(client, headers):
    return client.post(
        "/trips",
        json={
            "destination_name": "Mahabaleshwar",
            "start_date": "2026-12-05",
            "end_date": "2026-12-06",
        },
        headers=headers,
    ).json()


def make_trip_with_user_activity(client, headers):
    trip = make_trip(client, headers)
    client.post(
        f"/trips/{trip['id']}/activities",
        json={
            "day_id": trip["days"][0]["id"],
            "name": "My own walk",
            "category": "ACTIVITY",
        },
        headers=headers,
    )
    return trip


def mock_master(monkeypatch, plan_data):
    from app.services import copilot_service as cs

    class FakeMaster:
        def __init__(self, llm=None):
            pass

        async def run(self, context):
            return AgentResult(
                agent_name="MasterAgent",
                status="ok",
                data={"plan": plan_data, "reasoning": "drafted a plan"},
                tool_calls=[],
                reasoning="drafted a plan",
            )

    monkeypatch.setattr(cs, "MasterAgent", FakeMaster)


PLAN = {
    "days": [
        {
            "day_number": 1,
            "activities": [
                {
                    "name": "Venna Lake boating",
                    "category": "ACTIVITY",
                    "duration_minutes": 90,
                    "estimated_cost": 300,
                    "reason": "classic spot",
                }
            ],
        }
    ],
    "reasoning": "drafted",
}


def test_copilot_persists_plan_on_empty_trip(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip(client, headers)
    mock_master(monkeypatch, PLAN)

    res = client.post(
        f"/trips/{trip['id']}/copilot",
        json={"message": "plan my trip"},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["suggestions"] is None
    assert "added 1 activities" in body["message"]["content"]

    itinerary = client.get(f"/trips/{trip['id']}/itinerary", headers=headers).json()
    total = sum(len(d["activities"]) for d in itinerary["days"])
    assert total == 1
    saved = itinerary["days"][0]["activities"][0]
    assert saved["source"] == "ai"
    assert saved["name"] == "Venna Lake boating"


def test_copilot_requires_approval_on_user_built_trip(client, monkeypatch):
    headers = auth_headers(client)
    trip = make_trip_with_user_activity(client, headers)
    mock_master(monkeypatch, PLAN)

    res = client.post(
        f"/trips/{trip['id']}/copilot",
        json={"message": "plan my trip"},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    sugg = body["suggestions"]
    assert sugg, "must return an approval suggestion, not persist"
    assert "without your approval" in body["message"]["content"]
    assert sugg[0]["changes"][0]["change_type"] == "add_activity"
    assert sugg[0]["changes"][0]["proposed_data"]["name"] == "Venna Lake boating"

    # nothing persisted before approval
    itinerary = client.get(f"/trips/{trip['id']}/itinerary", headers=headers).json()
    total = sum(len(d["activities"]) for d in itinerary["days"])
    assert total == 1  # only the user's own activity

    # accepting the suggestion applies it (existing approval protocol)
    accept = client.post(
        f"/trips/{trip['id']}/suggestions/{sugg[0]['suggestion_id']}/action",
        json={"action": "accept"},
        headers=headers,
    )
    assert accept.status_code == 200
    assert accept.json()["applied_changes"] == 1
    itinerary = client.get(f"/trips/{trip['id']}/itinerary", headers=headers).json()
    total = sum(len(d["activities"]) for d in itinerary["days"])
    assert total == 2
