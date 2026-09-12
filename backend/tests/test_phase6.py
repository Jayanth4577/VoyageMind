"""Phase 6 integration tests: copilot, suggestions, contingencies, what-if."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_voyagemind.db")

import pytest
from starlette.testclient import TestClient

from app.agents.context import AgentResult
from app.core.database import Base, engine
from app.main import create_app
from app.models import Contingency, Trip
from app.services import contingency_service


@pytest.fixture(autouse=True)
def db_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_tables):
    with TestClient(create_app()) as c:
        yield c


# -- Helpers --

def _auth_headers(client):
    """Register + login, return auth headers."""
    import uuid
    email = f"p6_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": "testpass123"},
    )
    resp = client.post(
        "/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_trip(client, headers):
    """Create a test trip."""
    resp = client.post(
        "/trips",
        json={
            "origin_name": "Bengaluru",
            "destination_name": "Goa",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "num_travelers": 4,
            "total_budget": 50000,
            "currency": "INR",
            "trip_style": "mixed",
        },
        headers=headers,
    )
    return resp.json()


class MockMasterAgent:
    def __init__(self, **kwargs):
        pass

    async def run(self, context):
        return AgentResult(
            agent_name="MasterAgent",
            status="ok",
            data={
                "reasoning": "Copilot test response",
                "suggestions": [{
                    "suggestion_id": "test-sugg-1",
                    "changes": [{
                        "change_type": "add_activity",
                        "target_day": 1,
                        "proposed_data": {
                            "name": "Museum Visit",
                            "category": "MUSEUM",
                            "indoor": True,
                            "estimated_cost": 300,
                        },
                        "problem": "Rain expected",
                        "reason": "Indoor alternative",
                    }],
                    "problem": "Weather risk",
                    "reasoning": "Rain on day 1",
                }],
            },
            tool_calls=[],
            reasoning="Copilot test response",
            confidence=0.8,
        )


# -- Test Classes --

class TestCopilotAPI:
    @pytest.mark.anyio
    async def test_copilot_send_message(self, client, monkeypatch):
        monkeypatch.setattr("app.services.copilot_service.MasterAgent", MockMasterAgent)
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/copilot",
            json={"message": "What should I do on day 1?"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert data["message"]["content"] == "Copilot test response"
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1

    @pytest.mark.anyio
    async def test_copilot_history_empty(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.get(f"/trips/{trip['id']}/copilot/history", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_copilot_history_after_message(self, client, monkeypatch):
        monkeypatch.setattr("app.services.copilot_service.MasterAgent", MockMasterAgent)
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        client.post(
            f"/trips/{trip['id']}/copilot",
            json={"message": "Hello!"},
            headers=headers,
        )

        resp = client.get(f"/trips/{trip['id']}/copilot/history", headers=headers)
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    @pytest.mark.anyio
    async def test_copilot_requires_auth(self, client):
        resp = client.post("/trips/fake-id/copilot", json={"message": "hi"})
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_copilot_wrong_trip_404(self, client):
        headers = _auth_headers(client)
        resp = client.post(
            "/trips/fake-id/copilot",
            json={"message": "hi"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestSuggestionAPI:
    @pytest.mark.anyio
    async def test_reject_suggestion(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/suggestions/fake-id/action",
            json={"action": "reject"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    @pytest.mark.anyio
    async def test_accept_suggestion_not_found(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/suggestions/fake-id/action",
            json={"action": "accept"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"

    @pytest.mark.anyio
    async def test_accept_suggestion_applies_changes(self, client, monkeypatch):
        monkeypatch.setattr("app.services.copilot_service.MasterAgent", MockMasterAgent)
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        client.post(
            f"/trips/{trip['id']}/copilot",
            json={"message": "help"},
            headers=headers,
        )

        resp = client.post(
            f"/trips/{trip['id']}/suggestions/test-sugg-1/action",
            json={"action": "accept"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "applied"
        assert data["applied_changes"] > 0

    @pytest.mark.anyio
    async def test_suggestion_creates_audit_event(self, client, monkeypatch):
        monkeypatch.setattr("app.services.copilot_service.MasterAgent", MockMasterAgent)
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        client.post(f"/trips/{trip['id']}/copilot", json={"message": "h"}, headers=headers)
        client.post(
            f"/trips/{trip['id']}/suggestions/test-sugg-1/action",
            json={"action": "accept"},
            headers=headers,
        )

        from app.core.database import SessionLocal
        from app.models import TripEvent
        db = SessionLocal()
        events = db.query(TripEvent).filter(TripEvent.trip_id == trip["id"]).all()
        assert any(e.kind == "suggestion_accepted" for e in events)
        db.close()

    @pytest.mark.anyio
    async def test_suggestion_cascade_returns_budget(self, client, monkeypatch):
        monkeypatch.setattr("app.services.copilot_service.MasterAgent", MockMasterAgent)
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        client.post(f"/trips/{trip['id']}/copilot", json={"message": "h"}, headers=headers)
        resp = client.post(
            f"/trips/{trip['id']}/suggestions/test-sugg-1/action",
            json={"action": "accept"},
            headers=headers,
        )
        data = resp.json()
        assert "cascade" in data
        assert "budget" in data["cascade"]


class TestContingencyAPI:
    @pytest.mark.anyio
    async def test_list_contingencies_empty(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.get(f"/trips/{trip['id']}/contingencies", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_create_and_list_contingency(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        from app.core.database import SessionLocal
        db = SessionLocal()
        c = Contingency(
            trip_id=trip["id"],
            plan_level="B",
            trigger="RAIN",
            condition="Rain > 50%",
            fallback_plan=[],
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        db.close()

        resp = client.get(f"/trips/{trip['id']}/contingencies", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.anyio
    async def test_accept_contingency(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        from app.core.database import SessionLocal
        db = SessionLocal()
        c = Contingency(
            trip_id=trip["id"],
            plan_level="B",
            trigger="RAIN",
            condition="Rain > 50%",
            fallback_plan=[],
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        c_id = c.id
        db.close()

        resp = client.post(
            f"/trips/{trip['id']}/contingencies/{c_id}/action",
            json={"action": "accept"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    @pytest.mark.anyio
    async def test_dismiss_contingency(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        from app.core.database import SessionLocal
        db = SessionLocal()
        c = Contingency(
            trip_id=trip["id"],
            plan_level="B",
            trigger="RAIN",
            condition="Rain > 50%",
            fallback_plan=[],
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        c_id = c.id
        db.close()

        resp = client.post(
            f"/trips/{trip['id']}/contingencies/{c_id}/action",
            json={"action": "dismiss"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"

    @pytest.mark.anyio
    async def test_contingency_wrong_trip_404(self, client):
        headers = _auth_headers(client)
        resp = client.post(
            "/trips/fake-id/contingencies/fake-id/action",
            json={"action": "accept"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestWhatIfAPI:
    @pytest.mark.anyio
    async def test_simulate_rain(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "rain", "parameters": {"days": [1]}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "impact_chain" in data
        assert isinstance(data["impact_chain"], list)

    @pytest.mark.anyio
    async def test_simulate_flight_delay(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "flight_delay", "parameters": {"delay_hours": 4}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["time_delta_minutes"] == 240

    @pytest.mark.anyio
    async def test_simulate_budget_change(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "budget_change", "parameters": {"new_budget": 30000}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "budget_delta" in resp.json()

    @pytest.mark.anyio
    async def test_simulate_fewer_travelers(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "fewer_travelers", "parameters": {"new_count": 2}},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_simulate_hotel_unavailable(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "hotel_unavailable", "parameters": {}},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_simulate_extra_day(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "extra_day", "parameters": {}},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_simulate_unknown_scenario(self, client):
        headers = _auth_headers(client)
        trip = _create_trip(client, headers)

        resp = client.post(
            f"/trips/{trip['id']}/simulate",
            json={"scenario": "alien_invasion", "parameters": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "Unknown scenario" in resp.json()["impact_chain"][0]


class TestContingencyService:
    def test_create_contingency_from_agent_result(self, client):
        from app.core.database import SessionLocal
        db = SessionLocal()
        headers = _auth_headers(client)
        trip_data = _create_trip(client, headers)
        trip = db.query(Trip).filter(Trip.id == trip_data["id"]).first()

        result = contingency_service.create_from_agent_result(
            db, trip,
            {
                "contingencies": [{
                    "plan_level": "B",
                    "trigger": "RAIN",
                    "condition": "Windy",
                    "fallback_plan": [],
                }]
            }
        )
        assert len(result) == 1
        assert result[0].trigger == "RAIN"
        db.close()

    def test_update_contingency_status(self, client):
        from app.core.database import SessionLocal
        db = SessionLocal()
        headers = _auth_headers(client)
        trip_data = _create_trip(client, headers)
        trip = db.query(Trip).filter(Trip.id == trip_data["id"]).first()

        c = Contingency(
            trip_id=trip.id,
            plan_level="B",
            trigger="RAIN",
            condition="T",
        )
        db.add(c)
        db.commit()

        updated = contingency_service.update_status(db, trip, c.id, "dismiss")
        assert updated.status == "dismissed"
        db.close()

    def test_invalid_contingency_action(self, client):
        from fastapi import HTTPException

        from app.core.database import SessionLocal
        db = SessionLocal()
        headers = _auth_headers(client)
        trip_data = _create_trip(client, headers)
        trip = db.query(Trip).filter(Trip.id == trip_data["id"]).first()

        c = Contingency(
            trip_id=trip.id,
            plan_level="B",
            trigger="RAIN",
            condition="T",
        )
        db.add(c)
        db.commit()

        with pytest.raises(HTTPException):
            contingency_service.update_status(db, trip, c.id, "explode")
        db.close()
