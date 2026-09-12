"""Phase 5 Agent & Orchestration tests.

All tests use **mocked LLM** and **mocked MCP tools** — no real external
calls.  The mocking strategy follows the existing pattern:
  - LLM:  monkeypatch the provider's ``generate`` / ``generate_structured``
  - MCP:  monkeypatch ``travel_mcp.<facade>.<method>`` with AsyncMock
"""
import json
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_voyagemind.db")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult, LLMStepResponse, ToolDefinition
from app.agents.master_agent import MasterAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.tools import TOOL_DEFINITIONS, execute_tool, tool_definitions_for
from app.agents.transport_agent import TransportAgent
from app.agents.accommodation_agent import AccommodationAgent
from app.agents.places_agent import PlacesAgent
from app.agents.route_agent import RouteAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.weather_risk_agent import WeatherRiskAgent
from app.agents.contingency_agent import ContingencyAgent
from app.core.database import Base, engine
from app.llm.provider import LLMError
from app.main import create_app
from app.schemas.agent_schema import GeneratedPlan


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_tables):
    with TestClient(create_app()) as c:
        yield c


def _register_and_login(client) -> tuple[str, dict]:
    """Create a test user and return (user_id, auth_headers)."""
    client.post("/auth/register", json={"email": "agent@test.com", "password": "pw12345678"})
    resp = client.post("/auth/login", json={"email": "agent@test.com", "password": "pw12345678"})
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def _create_trip(client, headers) -> str:
    """Create a test trip and return its id."""
    resp = client.post(
        "/trips",
        json={
            "destination_name": "Goa",
            "origin_name": "Bengaluru",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "num_travelers": 4,
            "total_budget": 50000,
            "currency": "INR",
            "trip_style": "relaxed",
            "constraints": "vegetarian food preferred",
            "preferences": {"interests": ["beach", "food", "temples"]},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _sample_context(trip_id: str = "test-trip-id") -> AgentContext:
    return AgentContext(
        trip_id=trip_id,
        trip_data={
            "id": trip_id,
            "origin_name": "Bengaluru",
            "destination_name": "Goa",
            "destination_lat": 15.2993,
            "destination_lng": 74.124,
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "num_travelers": 4,
            "total_budget": 50000,
            "currency": "INR",
            "trip_style": "relaxed",
            "constraints": "vegetarian food preferred",
            "preferences": {"interests": ["beach", "food", "temples"]},
            "days": [
                {"day_id": f"day-{i}", "day_number": i, "date": f"2026-10-0{i}"}
                for i in range(1, 6)
            ],
        },
        preferences={"interests": ["beach", "food", "temples"]},
        request="generate",
    )


# ── mock helpers ──────────────────────────────────────────────────────────────

class FakeLLM:
    """LLM provider that returns predetermined JSON responses."""

    name = "fake"

    def __init__(self, responses=None):
        self._responses = responses or []
        self._call_idx = 0

    async def generate(self, prompt, *, system=None, temperature=0.7):
        if self._call_idx < len(self._responses):
            r = self._responses[self._call_idx]
            self._call_idx += 1
            return json.dumps(r) if isinstance(r, dict) else r
        # Default: immediate done response
        return json.dumps({"done": True, "tool_calls": [], "final_answer": {}, "reasoning": "default"})

    async def generate_structured(self, prompt, schema, *, system=None, temperature=0.2):
        if self._call_idx < len(self._responses):
            r = self._responses[self._call_idx]
            self._call_idx += 1
            if isinstance(r, dict):
                return schema.model_validate(r)
            return schema.model_validate(json.loads(r))
        raise LLMError("No more responses in FakeLLM")


# ── 1. Tool registry & execution ─────────────────────────────────────────────

class TestToolRegistry:
    def test_tool_definitions_exist(self):
        assert len(TOOL_DEFINITIONS) >= 10

    def test_tool_definitions_for_subset(self):
        subset = tool_definitions_for("get_weather", "geocode_place")
        assert len(subset) == 2
        names = {t.name for t in subset}
        assert names == {"get_weather", "geocode_place"}

    def test_tool_definitions_for_unknown_returns_empty(self):
        subset = tool_definitions_for("nonexistent_tool")
        assert subset == []

    @pytest.mark.anyio
    async def test_execute_tool_weather(self, monkeypatch):
        mock_wx = AsyncMock(return_value={"source": "open-meteo", "daily": []})
        monkeypatch.setattr("app.agents.tools.travel_mcp.weather.get_weather", mock_wx)

        trace = await execute_tool("get_weather", {"latitude": 15.3, "longitude": 74.1, "days": 5})
        assert trace.tool == "get_weather"
        assert trace.error is None
        assert trace.result["source"] == "open-meteo"
        mock_wx.assert_called_once_with(latitude=15.3, longitude=74.1, days=5)

    @pytest.mark.anyio
    async def test_execute_tool_unknown_returns_error(self):
        trace = await execute_tool("no_such_tool", {})
        assert trace.result["status"] == "error"
        assert "Unknown tool" in trace.result["error"]

    @pytest.mark.anyio
    async def test_execute_tool_exception_captured(self, monkeypatch):
        mock_geo = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("app.agents.tools.travel_mcp.maps.geocode_place", mock_geo)

        trace = await execute_tool("geocode_place", {"name": "Goa"})
        assert trace.error is not None
        assert "boom" in trace.error


# ── 2. Base agent orchestrator loop ──────────────────────────────────────────

class ConcreteAgent(BaseAgent):
    name = "test_agent"
    description = "Test agent"

    def system_prompt(self):
        return "You are a test agent."

    def available_tools(self):
        return tool_definitions_for("geocode_place")

    def _build_user_prompt(self, context):
        return f"Test prompt for trip {context.trip_id}"


class TestBaseAgent:
    @pytest.mark.anyio
    async def test_immediate_done(self):
        """LLM returns done=True on first call → agent returns immediately."""
        fake = FakeLLM([
            {"done": True, "tool_calls": [], "final_answer": {"key": "val"}, "reasoning": "ok"},
        ])
        agent = ConcreteAgent(llm=fake)
        result = await agent.run(_sample_context())
        assert result.status == "ok"
        assert result.data["key"] == "val"
        assert result.reasoning == "ok"

    @pytest.mark.anyio
    async def test_tool_call_then_done(self, monkeypatch):
        """LLM requests a tool call, gets results, then produces final answer."""
        mock_geo = AsyncMock(return_value={
            "source": "mock", "results": [{"name": "Goa", "latitude": 15.3, "longitude": 74.1}]
        })
        monkeypatch.setattr("app.agents.tools.travel_mcp.maps.geocode_place", mock_geo)

        fake = FakeLLM([
            # Step 1: request tool call
            {"done": False, "tool_calls": [{"tool": "geocode_place", "arguments": {"name": "Goa"}}], "final_answer": {}, "reasoning": ""},
            # Step 2: final answer using tool result
            {"done": True, "tool_calls": [], "final_answer": {"lat": 15.3, "lng": 74.1}, "reasoning": "got coords"},
        ])
        agent = ConcreteAgent(llm=fake)
        result = await agent.run(_sample_context())
        assert result.status == "ok"
        assert result.data["lat"] == 15.3
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool == "geocode_place"
        mock_geo.assert_called_once()

    @pytest.mark.anyio
    async def test_max_iterations_reached(self):
        """Agent hits max_iterations without done=True → returns partial."""
        fake = FakeLLM([
            {"done": False, "tool_calls": [], "final_answer": {}, "reasoning": ""},
        ] * 10)
        agent = ConcreteAgent(llm=fake)
        agent.max_iterations = 2
        result = await agent.run(_sample_context())
        # On last iteration it should still return something
        assert result.agent_name == "test_agent"

    @pytest.mark.anyio
    async def test_llm_error_graceful_degradation(self):
        """LLM raises LLMError → agent returns error status."""
        class BrokenLLM:
            name = "broken"
            async def generate(self, *a, **k):
                raise LLMError("API key invalid")

        agent = ConcreteAgent(llm=BrokenLLM())
        result = await agent.run(_sample_context())
        assert result.status == "error"
        assert "API key invalid" in result.reasoning

    @pytest.mark.anyio
    async def test_malformed_llm_response(self):
        """LLM returns non-JSON → agent degrades gracefully."""
        class GarbledLLM:
            name = "garbled"
            async def generate(self, *a, **k):
                return "This is not JSON at all, just plain text."

        agent = ConcreteAgent(llm=GarbledLLM())
        result = await agent.run(_sample_context())
        # Should still return a result (the parse fallback treats it as done)
        assert result.agent_name == "test_agent"


# ── 3. Master agent intent parsing ───────────────────────────────────────────

class TestMasterAgent:
    @pytest.mark.anyio
    async def test_default_intent_is_generate(self):
        """Empty request defaults to 'generate' intent."""
        ctx = _sample_context()
        ctx.request = ""

        # Mock the planner so we don't run the full pipeline
        with patch.object(PlannerAgent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = AgentResult(
                agent_name="PlannerAgent", status="ok", data={"plan": {}}, reasoning="done"
            )
            master = MasterAgent(llm=FakeLLM())
            result = await master.run(ctx)
            mock_run.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_intent_parsed(self):
        """When request says 'generate', it delegates to PlannerAgent."""
        from app.agents.master_agent import IntentSchema

        fake = FakeLLM([{"intent": "generate", "reasoning": "user wants a plan"}])
        ctx = _sample_context()

        with patch.object(PlannerAgent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = AgentResult(
                agent_name="PlannerAgent", status="ok", data={}, reasoning="done"
            )
            master = MasterAgent(llm=fake)
            result = await master.run(ctx)
            assert result.agent_name == "PlannerAgent"

    @pytest.mark.anyio
    async def test_check_weather_intent(self):
        """Weather intent delegates to WeatherRiskAgent."""
        from app.agents.master_agent import IntentSchema

        fake = FakeLLM([
            {"intent": "check_weather", "reasoning": "check rain"},
            # Response for the weather risk agent's own LLM call
            {"done": True, "tool_calls": [], "final_answer": {"overall_risk_level": "low"}, "reasoning": "no risk"},
        ])
        ctx = _sample_context()
        master = MasterAgent(llm=fake)
        result = await master.run(ctx)
        assert result.agent_name == "weather_risk"


# ── 4. Domain agent construction ─────────────────────────────────────────────

class TestDomainAgents:
    """Verify each domain agent is properly constructed."""

    def test_transport_agent(self):
        agent = TransportAgent()
        assert agent.name == "transport"
        assert agent.max_iterations == 3
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "search_transport" in names

    def test_accommodation_agent(self):
        agent = AccommodationAgent()
        assert agent.name == "accommodation"
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "search_stays" in names

    def test_places_agent(self):
        agent = PlacesAgent()
        assert agent.name == "places"
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "search_places" in names
        assert "find_nearby_places" in names

    def test_route_agent(self):
        agent = RouteAgent()
        assert agent.name == "route"
        assert agent.max_iterations == 2
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "calculate_route" in names
        assert "optimize_route" in names

    def test_budget_agent(self):
        agent = BudgetAgent()
        assert agent.name == "budget"
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "search_stays" in names
        assert "search_transport" in names

    def test_weather_risk_agent(self):
        agent = WeatherRiskAgent()
        assert agent.name == "weather_risk"
        assert agent.max_iterations == 2
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "get_weather" in names

    def test_contingency_agent(self):
        agent = ContingencyAgent()
        assert agent.name == "contingency"
        tools = agent.available_tools()
        names = {t.name for t in tools}
        assert "search_places" in names
        assert "search_transport" in names


# ── 5. Transport agent with tool call ────────────────────────────────────────

class TestTransportAgentRun:
    @pytest.mark.anyio
    async def test_transport_agent_calls_tool(self, monkeypatch):
        mock_transport = AsyncMock(return_value={
            "source": "demo", "is_mock": True,
            "offers": [
                {"kind": "flight", "provider": "IndiGo", "price": 4500, "currency": "INR",
                 "duration_minutes": 75, "departure_at": "08:00", "arrival_at": "09:15"},
            ],
        })
        monkeypatch.setattr("app.agents.tools.travel_mcp.flights.search_transport", mock_transport)

        fake = FakeLLM([
            # Step 1: request transport search
            {"done": False, "tool_calls": [
                {"tool": "search_transport", "arguments": {"origin": "Bengaluru", "destination": "Goa", "date": "2026-10-01"}}
            ], "final_answer": {}, "reasoning": ""},
            # Step 2: final answer with ranked options
            {"done": True, "tool_calls": [], "final_answer": {
                "options": [{"kind": "flight", "provider": "IndiGo", "price": 4500}],
                "recommendation": "IndiGo flight",
                "reasoning": "Cheapest and fastest"
            }, "reasoning": "ranked by price"},
        ])
        agent = TransportAgent(llm=fake)
        result = await agent.run(_sample_context())
        assert result.status == "ok"
        assert len(result.tool_calls) == 1


# ── 6. Weather risk agent ────────────────────────────────────────────────────

class TestWeatherRiskAgentRun:
    @pytest.mark.anyio
    async def test_rain_risk_detected(self, monkeypatch):
        mock_wx = AsyncMock(return_value={
            "source": "open-meteo", "is_mock": False,
            "daily": [
                {"date": "2026-10-01", "rain_probability": 80, "precipitation_mm": 12, "temp_max_c": 30},
                {"date": "2026-10-02", "rain_probability": 10, "precipitation_mm": 0, "temp_max_c": 32},
            ],
        })
        monkeypatch.setattr("app.agents.tools.travel_mcp.weather.get_weather", mock_wx)

        fake = FakeLLM([
            # Step 1: request weather tool
            {"done": False, "tool_calls": [
                {"tool": "get_weather", "arguments": {"latitude": 15.3, "longitude": 74.1, "days": 5}}
            ], "final_answer": {}, "reasoning": ""},
            # Step 2: analyze results
            {"done": True, "tool_calls": [], "final_answer": {
                "days_at_risk": [
                    {"day_number": 1, "risk": "rain", "reasons": ["80% rain prob", "12mm precip"],
                     "affected_activities": ["Beach"], "suggestions": [
                        {"type": "swap_indoor", "activity": "Beach", "alternative": "Museum", "reason": "heavy rain", "confidence": "0.9"}
                    ]}
                ],
                "overall_risk_level": "moderate",
                "reasoning": "Day 1 has heavy rain"
            }, "reasoning": "rain on day 1"},
        ])
        agent = WeatherRiskAgent(llm=fake)
        result = await agent.run(_sample_context())
        assert result.status == "ok"
        assert result.data.get("overall_risk_level") == "moderate"


# ── 7. Planner pipeline ─────────────────────────────────────────────────────

class TestPlannerPipeline:
    @pytest.mark.anyio
    async def test_planner_produces_plan(self, monkeypatch):
        """Mock all sub-agents, verify planner assembles a GeneratedPlan."""
        mock_plan = GeneratedPlan(
            days=[{
                "day_number": 1,
                "title": "Arrival Day",
                "activities": [{
                    "name": "Baga Beach",
                    "category": "BEACH",
                    "location_name": "Baga Beach, Goa",
                    "latitude": 15.5553,
                    "longitude": 73.7514,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "duration_minutes": 120,
                    "estimated_cost": 0,
                    "weather_sensitive": True,
                    "indoor": False,
                    "reason": "Popular beach",
                    "confidence": 0.9,
                }],
                "notes": "Relax after travel",
            }],
            reasoning="Test plan",
        )

        # Mock each sub-agent's run method
        for agent_cls in [TransportAgent, AccommodationAgent, PlacesAgent, WeatherRiskAgent]:
            monkeypatch.setattr(
                agent_cls, "run",
                AsyncMock(return_value=AgentResult(
                    agent_name=agent_cls.name, status="ok", data={"test": True}, reasoning="mocked"
                ))
            )

        # Mock the LLM's generate_structured for the assembly step
        fake = FakeLLM()
        fake._responses = [mock_plan.model_dump()]
        planner = PlannerAgent(llm=fake)
        result = await planner.run(_sample_context())

        assert result.status == "ok"
        plan_data = result.data.get("plan")
        assert plan_data is not None


# ── 8. Generate API endpoint ────────────────────────────────────────────────

class TestGenerateAPI:
    def test_generate_endpoint_exists(self, client):
        """Verify the endpoint is registered (will return 401 without auth)."""
        resp = client.post("/trips/fake-id/generate")
        assert resp.status_code == 401

    def test_generate_with_mocked_agent(self, client, monkeypatch):
        """Full HTTP test: create trip → generate → verify activities persisted."""
        _, headers = _register_and_login(client)
        trip_id = _create_trip(client, headers)

        # Mock the MasterAgent to return a plan with activities
        mock_result = AgentResult(
            agent_name="MasterAgent",
            status="ok",
            data={
                "plan": {
                    "days": [
                        {
                            "day_number": 1,
                            "title": "Arrival Day",
                            "activities": [
                                {
                                    "name": "Baga Beach",
                                    "category": "BEACH",
                                    "location_name": "Baga, North Goa",
                                    "latitude": 15.5553,
                                    "longitude": 73.7514,
                                    "start_time": "10:00",
                                    "end_time": "12:00",
                                    "duration_minutes": 120,
                                    "estimated_cost": 0,
                                    "weather_sensitive": True,
                                    "indoor": False,
                                    "reason": "Popular beach",
                                    "confidence": 0.9,
                                },
                                {
                                    "name": "Britto's Restaurant",
                                    "category": "RESTAURANT",
                                    "location_name": "Baga Beach Road",
                                    "start_time": "13:00",
                                    "end_time": "14:30",
                                    "duration_minutes": 90,
                                    "estimated_cost": 1200,
                                    "weather_sensitive": False,
                                    "indoor": True,
                                    "reason": "Famous Goan food",
                                    "confidence": 0.85,
                                },
                            ],
                            "notes": "Relax after travel",
                        },
                    ],
                    "reasoning": "Planned arrival day",
                },
                "transport": {"options": []},
                "accommodation": {"options": []},
                "weather": {"overall_risk_level": "low"},
            },
            tool_calls=[],
            reasoning="Generated plan",
        )

        class MockMasterAgent:
            def __init__(self, **kwargs):
                pass
            async def run(self, context):
                return mock_result

        # Patch the class itself at the module where the endpoint imports it
        monkeypatch.setattr("app.api.agents.MasterAgent", MockMasterAgent)

        resp = client.post(f"/trips/{trip_id}/generate", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["trip_id"] == trip_id

        # Verify activities were persisted
        itin = client.get(f"/trips/{trip_id}/itinerary", headers=headers).json()
        day1_activities = [
            a for d in itin["days"] if d["day_number"] == 1 for a in d["activities"]
        ]
        assert len(day1_activities) == 2
        names = {a["name"] for a in day1_activities}
        assert "Baga Beach" in names
        assert "Britto's Restaurant" in names

        # Verify AI source flags
        beach = next(a for a in day1_activities if a["name"] == "Baga Beach")
        assert beach["source"] == "ai"
        assert beach["ai_recommended"] is True
        assert beach["user_selected"] is False

        # Verify budget synced for the restaurant
        budget_resp = client.get(f"/trips/{trip_id}/budget", headers=headers)
        assert budget_resp.status_code == 200
        budget = budget_resp.json()
        assert budget["spent"] > 0  # at least the restaurant cost

    def test_generate_trip_not_found(self, client):
        _, headers = _register_and_login(client)
        resp = client.post("/trips/nonexistent/generate", headers=headers)
        assert resp.status_code == 404

    def test_generate_wrong_owner(self, client):
        _, headers1 = _register_and_login(client)
        trip_id = _create_trip(client, headers1)

        # Register a second user
        client.post("/auth/register", json={"email": "other@test.com", "password": "pw12345678"})
        resp = client.post("/auth/login", json={"email": "other@test.com", "password": "pw12345678"})
        headers2 = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        resp = client.post(f"/trips/{trip_id}/generate", headers=headers2)
        assert resp.status_code == 404


# ── 9. Recommendations API ──────────────────────────────────────────────────

class TestRecommendationsAPI:
    def test_recommendations_empty(self, client):
        _, headers = _register_and_login(client)
        trip_id = _create_trip(client, headers)
        resp = client.get(f"/trips/{trip_id}/recommendations", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_recommendations_requires_auth(self, client):
        resp = client.get("/trips/fake/recommendations")
        assert resp.status_code == 401


# ── 10. Context & schema models ─────────────────────────────────────────────

class TestSchemas:
    def test_agent_context_defaults(self):
        ctx = AgentContext(trip_id="t1")
        assert ctx.trip_data == {}
        assert ctx.prior_results == {}
        assert ctx.request == ""

    def test_agent_result_serializable(self):
        r = AgentResult(agent_name="test", data={"k": [1, 2]})
        d = r.model_dump()
        assert d["agent_name"] == "test"

    def test_llm_step_response_parse(self):
        step = LLMStepResponse(done=True, final_answer={"x": 1}, reasoning="ok")
        assert step.done
        assert step.final_answer == {"x": 1}

    def test_generated_plan_schema(self):
        plan = GeneratedPlan(
            days=[{"day_number": 1, "title": "Day 1", "activities": [], "notes": ""}],
            reasoning="test",
        )
        assert len(plan.days) == 1
        assert plan.days[0].day_number == 1
