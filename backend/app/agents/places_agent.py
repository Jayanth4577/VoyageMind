"""Places Agent — deterministic multi-category POI discovery.

The search itself is mechanical (geocode destination, sweep nearby categories),
so it runs as straight-line code instead of LLM tool orchestration — a lite
model skipping searches produced single-activity itineraries. The LLM's real
judgment happens later, in the PlannerAgent assembly step, which selects from
this pool.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from app.agents.context import AgentContext, AgentResult, ToolDefinition, ToolTrace
from app.agents.tools import execute_tool, tool_definitions_for

logger = logging.getLogger(__name__)

# Sweep order — hill stations want viewpoints/waterfalls, cities want markets.
SWEEP_CATEGORIES = (
    "attraction",
    "viewpoint",
    "temple",
    "market",
    "restaurant",
    "museum",
    "garden",
    "waterfall",
    "monument",
    "cafe",
)
NEARBY_RADIUS_M = 15000
TARGET_PLACES = 30


class PlacesAgent:
    name: ClassVar[str] = "places"
    description: ClassVar[str] = (
        "Specializes in finding activities, attractions, and dining options."
    )

    def __init__(self, *, llm=None):
        self._llm = llm
        self.max_iterations = 1  # deterministic flow: no LLM loop needed

    def system_prompt(self) -> str:
        return "Places are gathered deterministically via nearby-POI sweeps."

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("search_places", "find_nearby_places", "geocode_place")

    async def run(self, context: AgentContext) -> AgentResult:
        trip = context.trip_data
        destination = trip.get("destination_name") or ""
        traces: list[ToolTrace] = []

        # 1. Coordinates: trip row first, else geocode the destination name.
        latitude = trip.get("destination_lat")
        longitude = trip.get("destination_lng")
        if latitude is None or longitude is None:
            geo = await execute_tool("geocode_place", {"name": destination})
            traces.append(geo)
            results = (geo.result or {}).get("results") or []
            if results:
                latitude = results[0].get("latitude")
                longitude = results[0].get("longitude")

        activities: list[dict] = []
        seen_names: set[str] = set()

        # 2. Deterministic category sweeps around the destination.
        if latitude is not None and longitude is not None:
            for category in SWEEP_CATEGORIES:
                if len(activities) >= TARGET_PLACES:
                    break
                sweep = await execute_tool(
                    "find_nearby_places",
                    {
                        "latitude": latitude,
                        "longitude": longitude,
                        "category": category,
                        "radius_m": NEARBY_RADIUS_M,
                    },
                )
                traces.append(sweep)
                for place in (sweep.result or {}).get("results") or []:
                    name = (place.get("name") or "").strip()
                    lowered = name.lower()
                    if not name or lowered in seen_names or lowered.startswith("(unnamed)"):
                        continue
                    seen_names.add(lowered)
                    activities.append(
                        {
                            "name": name,
                            "category": category.upper(),
                            "location_name": destination,
                            "latitude": place.get("latitude"),
                            "longitude": place.get("longitude"),
                            "estimated_duration_minutes": 60,
                            "estimated_cost": 0,
                            "weather_sensitive": category
                            in ("viewpoint", "waterfall", "garden", "beach"),
                            "indoor": category in ("museum", "cafe", "restaurant", "market"),
                            "reason": (
                                f"{category.title()} found "
                                f"{place.get('distance_km', '?')} km away"
                            ),
                            "data_source": (sweep.result or {}).get("source", "openstreetmap"),
                        }
                    )

        # 3. Free-text search as a fallback when POI sweeps came back thin.
        if len(activities) < 5 and destination:
            search = await execute_tool(
                "search_places",
                {"query": f"{destination} tourist attractions", "count": 8},
            )
            traces.append(search)
            for place in (search.result or {}).get("results") or []:
                name = (place.get("name") or "").strip()
                if not name or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
                activities.append(
                    {
                        "name": name,
                        "category": "ATTRACTION",
                        "location_name": place.get("display_name") or destination,
                        "latitude": place.get("latitude"),
                        "longitude": place.get("longitude"),
                        "estimated_duration_minutes": 60,
                        "estimated_cost": 0,
                        "weather_sensitive": True,
                        "indoor": False,
                        "reason": "Notable spot from place search",
                        "data_source": (search.result or {}).get("source", "nominatim"),
                    }
                )

        logger.info(
            "PlacesAgent gathered %d places for %s (%d tool calls)",
            len(activities),
            destination,
            len(traces),
        )
        return AgentResult(
            agent_name="places",
            status="ok" if activities else "partial",
            data={
                "activities": activities,
                "reasoning": (
                    f"Gathered {len(activities)} places around {destination} via "
                    f"{len(SWEEP_CATEGORIES)} category sweeps."
                    if activities
                    else f"No places found near {destination}"
                ),
            },
            tool_calls=traces,
            reasoning=f"Gathered {len(activities)} places for {destination}",
            confidence=0.9 if activities else 0.3,
        )
