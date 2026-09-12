"""Tool registry — maps tool names to executable async functions.

Every tool wraps a Travel MCP facade method or a backend deterministic service.
The registry provides JSON-schema definitions so the LLM can request tool
calls, and an executor that dispatches by name and catches all exceptions into
structured error responses (spec §25 resilience contract).
"""
from __future__ import annotations

import time

from app.agents.context import ToolDefinition, ToolTrace
from app.core.logging import get_logger
from app.mcp.travel_mcp import travel_mcp
from app.services import (
    budget_service,
    conflict_service,
    optimization_service,
    route_service,
    weather_service,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (JSON-schema descriptions for the LLM)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_weather",
        description=(
            "Get weather forecast for a location. Returns daily forecasts with "
            "temperature, rain probability, precipitation, and risk flags."
        ),
        parameters={
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "days": {"type": "integer", "default": 5},
            },
            "required": ["latitude", "longitude"],
        },
    ),
    ToolDefinition(
        name="geocode_place",
        description="Resolve a place name to latitude/longitude coordinates.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
    ToolDefinition(
        name="calculate_route",
        description=(
            "Calculate road distance and duration between a list of points. "
            "Each point needs latitude and longitude."
        ),
        parameters={
            "type": "object",
            "properties": {
                "points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"},
                        },
                        "required": ["latitude", "longitude"],
                    },
                }
            },
            "required": ["points"],
        },
    ),
    ToolDefinition(
        name="optimize_route",
        description="Find the best visiting order for a list of points to minimise travel time.",
        parameters={
            "type": "object",
            "properties": {
                "points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"},
                        },
                        "required": ["latitude", "longitude"],
                    },
                }
            },
            "required": ["points"],
        },
    ),
    ToolDefinition(
        name="search_places",
        description="Search for places / points of interest by a text query.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "count": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="find_nearby_places",
        description=(
            "Find nearby places around a location by category "
            "(restaurant, attraction, museum, beach, temple, market, cafe)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "category": {"type": "string", "default": "attraction"},
                "radius_m": {"type": "integer", "default": 2000},
            },
            "required": ["latitude", "longitude"],
        },
    ),
    ToolDefinition(
        name="search_transport",
        description="Search for transport options (flights, trains, buses) between two cities on a date.",
        parameters={
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["origin", "destination", "date"],
        },
    ),
    ToolDefinition(
        name="search_stays",
        description="Search for accommodation options at a location.",
        parameters={
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "YYYY-MM-DD"},
                "guests": {"type": "integer", "default": 2},
            },
            "required": ["location", "check_in", "check_out"],
        },
    ),
    ToolDefinition(
        name="get_exchange_rate",
        description="Get the exchange rate between two currencies (ISO 4217 codes).",
        parameters={
            "type": "object",
            "properties": {
                "base": {"type": "string"},
                "target": {"type": "string"},
            },
            "required": ["base", "target"],
        },
    ),
    ToolDefinition(
        name="web_search",
        description="Search the web for travel information, tips, or opening hours.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
]


def tool_definitions_for(*names: str) -> list[ToolDefinition]:
    """Return a subset of tool definitions by name (for agent-specific tool sets)."""
    name_set = set(names)
    return [t for t in TOOL_DEFINITIONS if t.name in name_set]


# ---------------------------------------------------------------------------
# Tool executor — dispatches by name
# ---------------------------------------------------------------------------


async def execute_tool(name: str, arguments: dict) -> ToolTrace:
    """Execute a tool by name and return a full trace record.

    Never raises — all errors are captured into the ToolTrace so the agent loop
    can feed the error message back to the LLM for recovery.
    """
    t0 = time.monotonic()
    try:
        result = await _dispatch(name, arguments)
        return ToolTrace(
            tool=name,
            arguments=arguments,
            result=result,
            duration_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool %s failed: %s", name, exc)
        return ToolTrace(
            tool=name,
            arguments=arguments,
            result={"status": "error", "error": str(exc)},
            duration_ms=round((time.monotonic() - t0) * 1000, 1),
            error=str(exc),
        )


async def _dispatch(name: str, args: dict) -> dict:
    """Route tool name to the correct MCP facade or service call."""
    match name:
        # -- Weather ---------------------------------------------------------
        case "get_weather":
            return await travel_mcp.weather.get_weather(
                latitude=args["latitude"],
                longitude=args["longitude"],
                days=args.get("days", 5),
            )
        # -- Maps / Places ---------------------------------------------------
        case "geocode_place":
            return await travel_mcp.maps.geocode_place(args["name"])
        case "calculate_route":
            return await travel_mcp.maps.calculate_route(args["points"])
        case "optimize_route":
            return await travel_mcp.maps.optimize_route(args["points"])
        case "search_places":
            return await travel_mcp.maps.search_places(
                args["query"], count=args.get("count", 5)
            )
        case "find_nearby_places":
            return await travel_mcp.maps.find_nearby_places(
                latitude=args["latitude"],
                longitude=args["longitude"],
                category=args.get("category", "attraction"),
                radius_m=args.get("radius_m", 2000),
            )
        # -- Transport / Stays / FX / Web ------------------------------------
        case "search_transport":
            return await travel_mcp.flights.search_transport(
                origin=args["origin"],
                destination=args["destination"],
                date=args["date"],
            )
        case "search_stays":
            return await travel_mcp.flights.search_stays(
                location=args["location"],
                check_in=args["check_in"],
                check_out=args["check_out"],
                guests=args.get("guests", 2),
            )
        case "get_exchange_rate":
            return await travel_mcp.flights.get_exchange_rate(
                base=args["base"], target=args["target"]
            )
        case "web_search":
            return await travel_mcp.flights.web_search(args["query"])
        # -- Unknown ---------------------------------------------------------
        case _:
            return {"status": "error", "error": f"Unknown tool: {name}"}
