"""Adaptive-radius tests for the PlacesAgent sweep."""
import asyncio
from unittest.mock import patch

from app.agents.context import AgentContext, ToolTrace
from app.agents.places_agent import PlacesAgent, initial_radius_m


def trace(tool: str, result: dict):
    return ToolTrace(tool=tool, result=result)


def geo_result(population=None):
    return {
        "results": [
            {"name": "Testville", "latitude": 17.92, "longitude": 73.67, "population": population}
        ]
    }


def nearby_result(names):
    return {"results": [{"name": n, "latitude": 17.9, "longitude": 73.6} for n in names]}


def make_context():
    return AgentContext(
        trip_id="t1",
        trip_data={"destination_name": "Testville"},
        request="generate",
    )


def test_initial_radius_by_population():
    assert initial_radius_m(None) == 15000  # unknown -> default
    assert initial_radius_m(12_000_000) == 6000  # metro
    assert initial_radius_m(500_000) == 10_000  # city
    assert initial_radius_m(80_000) == 15_000  # town
    assert initial_radius_m(2_000) == 20_000  # rural / hill station


def test_thin_first_pass_expands_radius():
    """Few results at the start radius -> the sweep re-runs at double radius."""
    calls = []

    async def fake_execute_tool(name, arguments):
        calls.append((name, dict(arguments or {})))
        if name == "geocode_place":
            return trace(name, geo_result(2_000))
        if name == "find_nearby_places":
            radius = arguments["radius_m"]
            if radius <= 15_000:
                # thin rural area: 1 result per category at 15 km
                return trace(name, nearby_result([f"{arguments['category']}-{radius}"]))
            # expanded 30/40 km sweeps return richer results
            return trace(
                name,
                nearby_result([f"{arguments['category']}-wide-{i}" for i in range(3)]),
            )
        if name == "search_places":
            return trace(name, {"results": []})
        return trace(name, {})

    agent = PlacesAgent()
    with patch("app.agents.places_agent.execute_tool", side_effect=fake_execute_tool):
        result = asyncio.run(agent.run(make_context()))

    activities = result.data["activities"]
    assert len(activities) >= 8  # expansion rescued the pool
    radius_sequence = [a["radius_m"] for n, a in calls if n == "find_nearby_places"]
    assert max(radius_sequence) > 15_000  # expansion actually happened
    assert max(radius_sequence) <= 40_000  # distance sanity cap respected


def test_dense_metro_starts_tight_and_skips_expansion():
    """A metro with rich results at 6 km must never widen."""
    calls = []

    async def fake_execute_tool(name, arguments):
        calls.append((name, dict(arguments or {})))
        if name == "geocode_place":
            return trace(name, geo_result(8_000_000))
        if name == "find_nearby_places":
            return trace(
                name, nearby_result([f"{arguments['category']}-{i}" for i in range(5)])
            )
        return trace(name, {})

    agent = PlacesAgent()
    with patch("app.agents.places_agent.execute_tool", side_effect=fake_execute_tool):
        result = asyncio.run(agent.run(make_context()))

    assert len(result.data["activities"]) >= 8
    radii = [a["radius_m"] for n, a in calls if n == "find_nearby_places"]
    assert set(radii) == {6000}  # stayed at the tight metro radius
