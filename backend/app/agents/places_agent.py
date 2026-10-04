"""Places Agent — adaptive multi-category POI discovery.

The search itself is mechanical (geocode destination, sweep nearby
categories), so it runs as straight-line code instead of LLM tool
orchestration — a lite model skipping searches produced single-activity
itineraries. The LLM's real judgment happens later, in the PlannerAgent
assembly step, which selects from this pool.

Radius is adaptive in two dimensions:
    1. Place-type aware start: the geocoder's population figure sizes the
       first sweep — dense metros are searched tight, rural/hill areas wide.
    2. Expansion passes: if the pool comes back thin, the radius doubles and
       sparse categories are re-swept (up to a distance sanity cap).
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

DEFAULT_RADIUS_M = 15000
MAX_RADIUS_M = 40000
EXPANSION_THRESHOLD = 8  # below this many places, widen and re-sweep
MAX_EXPANSIONS = 2  # 15 km -> 30 km -> 40 km at most
TARGET_PLACES = 30


def initial_radius_m(population: int | None) -> int:
    """Starting sweep radius sized to how dense the destination is.

    POI density tracks population: a metro is saturated within a few km while
    a hill station's viewpoints scatter across tens of kilometres.
    """
    if population is None:
        return DEFAULT_RADIUS_M
    if population >= 1_000_000:
        return 6000
    if population >= 200_000:
        return 10_000
    if population >= 50_000:
        return 15_000
    return 20_000


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

        # 1. Coordinates + population: trip row first, else geocode.
        latitude = trip.get("destination_lat")
        longitude = trip.get("destination_lng")
        population = None
        if latitude is None or longitude is None:
            geo = await execute_tool("geocode_place", {"name": destination})
            traces.append(geo)
            results = (geo.result or {}).get("results") or []
            if results:
                latitude = results[0].get("latitude")
                longitude = results[0].get("longitude")
                population = results[0].get("population")

        activities: list[dict] = []
        seen_names: set[str] = set()
        radius_m = initial_radius_m(population)

        # 2. Adaptive category sweeps.
        if latitude is not None and longitude is not None:
            activities, traces = await self._sweep_pass(
                destination,
                latitude,
                longitude,
                radius_m,
                activities,
                seen_names,
                traces,
            )

            expansions = 0
            while (
                len(activities) < EXPANSION_THRESHOLD
                and expansions < MAX_EXPANSIONS
                and radius_m < MAX_RADIUS_M
            ):
                expansions += 1
                radius_m = min(radius_m * 2, MAX_RADIUS_M)
                logger.info(
                    "Thin pool (%d places) for %s — expanding sweep to %d m",
                    len(activities),
                    destination,
                    radius_m,
                )
                activities, traces = await self._sweep_pass(
                    destination,
                    latitude,
                    longitude,
                    radius_m,
                    activities,
                    seen_names,
                    traces,
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
            "PlacesAgent gathered %d places for %s (radius %d m, %d tool calls)",
            len(activities),
            destination,
            radius_m,
            len(traces),
        )
        return AgentResult(
            agent_name="places",
            status="ok" if activities else "partial",
            data={
                "activities": activities,
                "reasoning": (
                    f"Gathered {len(activities)} places around {destination} "
                    f"sweeping {len(SWEEP_CATEGORIES)} categories out to "
                    f"{radius_m / 1000:.0f} km."
                    if activities
                    else f"No places found near {destination}"
                ),
            },
            tool_calls=traces,
            reasoning=f"Gathered {len(activities)} places for {destination}",
            confidence=0.9 if activities else 0.3,
        )

    async def _sweep_pass(
        self,
        destination: str,
        latitude: float,
        longitude: float,
        radius_m: int,
        activities: list[dict],
        seen_names: set[str],
        traces: list[ToolTrace],
    ) -> tuple[list[dict], list[ToolTrace]]:
        """One full category sweep at the given radius; returns updated pool."""
        for category in SWEEP_CATEGORIES:
            if len(activities) >= TARGET_PLACES:
                break
            sweep = await execute_tool(
                "find_nearby_places",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "category": category,
                    "radius_m": radius_m,
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
        return activities, traces
