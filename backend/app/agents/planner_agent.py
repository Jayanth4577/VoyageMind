"""PlannerAgent — end-to-end plan generation pipeline (Mode A, spec §5.3).

Orchestrates the full trip planning pipeline:
    1. Search transport options (TransportAgent)
    2. Search accommodation options (AccommodationAgent)
    3. Find places / activities (PlacesAgent)
    4. Check weather risks (WeatherRiskAgent)
    5. Assemble a coherent daily itinerary (LLM reasoning)

The LLM NEVER invents data — it selects and arranges from tool results.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.context import AgentContext, AgentResult, ToolTrace
from app.core.logging import get_logger
from app.llm import LLMError, get_llm_provider
from app.llm.provider import LLMProvider
from app.schemas.agent_schema import GeneratedPlan

logger = get_logger(__name__)

ASSEMBLY_SYSTEM = """\
You are an expert travel planner. Given real data from tool searches (places, \
transport, accommodation, weather), assemble a coherent daily itinerary.

RULES:
- ONLY use activities, costs, and locations from the provided tool data.
- NEVER invent prices, coordinates, ratings, or durations.
- Assign start_time / end_time as "HH:MM" 24h strings. Leave empty ("") if uncertain.
- Set duration_minutes from source data or reasonable estimate (60-120 min for typical activities).
- Set weather_sensitive=true and indoor=false for outdoor activities (beaches, hikes, etc).
- Set indoor=true for museums, restaurants, shopping.
- Distribute activities sensibly — morning sightseeing, midday food, evening dining.
- On rainy days (from weather data), prefer indoor activities.
- Keep per-day activities to 3-5 for a comfortable pace (or more for adventure style).
- Respond ONLY with valid JSON matching the GeneratedPlan schema.
"""


class PlannerAgent:
    """End-to-end plan generation pipeline (Mode A)."""

    def __init__(self, *, llm: LLMProvider | None = None) -> None:
        self._llm = llm or get_llm_provider()

    async def run(self, context: AgentContext) -> AgentResult:
        logger.info("PlannerAgent starting generation pipeline for trip %s", context.trip_id)

        results: dict[str, Any] = {}
        all_traces: list[ToolTrace] = []

        try:
            from app.agents.accommodation_agent import AccommodationAgent
            from app.agents.places_agent import PlacesAgent
            from app.agents.transport_agent import TransportAgent
            from app.agents.weather_risk_agent import WeatherRiskAgent

            # Step 1: Search transport
            transport_agent = TransportAgent(llm=self._llm)
            transport_res = await transport_agent.run(context)
            results["transport"] = transport_res.data
            all_traces.extend(transport_res.tool_calls)

            # Step 2: Search accommodation
            enriched = context.model_copy(
                update={"prior_results": {**context.prior_results, **results}}
            )
            acc_agent = AccommodationAgent(llm=self._llm)
            acc_res = await acc_agent.run(enriched)
            results["accommodation"] = acc_res.data
            all_traces.extend(acc_res.tool_calls)

            # Step 3: Find places / activities
            enriched = context.model_copy(
                update={"prior_results": {**context.prior_results, **results}}
            )
            places_agent = PlacesAgent(llm=self._llm)
            places_res = await places_agent.run(enriched)
            results["places"] = places_res.data
            all_traces.extend(places_res.tool_calls)

            # Step 4: Check weather
            enriched = context.model_copy(
                update={"prior_results": {**context.prior_results, **results}}
            )
            weather_agent = WeatherRiskAgent(llm=self._llm)
            weather_res = await weather_agent.run(enriched)
            results["weather"] = weather_res.data
            all_traces.extend(weather_res.tool_calls)

            # Step 5: Assemble daily itinerary via LLM
            plan = await self._assemble_itinerary(context, results)
            results["plan"] = plan.model_dump()

            return AgentResult(
                agent_name="PlannerAgent",
                status="ok",
                data=results,
                tool_calls=all_traces,
                reasoning=plan.reasoning or "Generated complete plan",
                confidence=0.8,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("PlannerAgent pipeline failed: %s", exc)
            return AgentResult(
                agent_name="PlannerAgent",
                status="error",
                data=results,
                tool_calls=all_traces,
                reasoning=f"Pipeline error: {exc}",
                confidence=0.0,
            )

    async def _assemble_itinerary(
        self, context: AgentContext, results: dict[str, Any]
    ) -> GeneratedPlan:
        trip = context.trip_data
        n_days = len(trip.get("days", []))

        # Truncate large data sections to fit in LLM context
        places_str = json.dumps(results.get("places", {}), indent=2, default=str)
        if len(places_str) > 4000:
            places_str = places_str[:4000] + "\n... (truncated)"
        weather_str = json.dumps(results.get("weather", {}), indent=2, default=str)
        if len(weather_str) > 2000:
            weather_str = weather_str[:2000] + "\n... (truncated)"
        transport_str = json.dumps(results.get("transport", {}), indent=2, default=str)
        if len(transport_str) > 1500:
            transport_str = transport_str[:1500] + "\n... (truncated)"

        prompt = f"""\
Assemble a {n_days}-day daily itinerary for this trip.

## Trip Details
- Origin: {trip.get("origin_name", "N/A")}
- Destination: {trip.get("destination_name", "N/A")}
- Travelers: {trip.get("num_travelers", 1)}
- Budget: {trip.get("total_budget", "not set")} {trip.get("currency", "INR")}
- Style: {trip.get("trip_style", "mixed")}
- Constraints: {trip.get("constraints", "none")}

## Available Places & Activities (from tool searches)
{places_str}

## Weather Forecast & Risks
{weather_str}

## Transport Options
{transport_str}

## Output
Return a JSON object with this schema:
{{
  "days": [
    {{
      "day_number": 1,
      "title": "Arrival & Beach Day",
      "activities": [
        {{
          "name": "str",
          "category": "BEACH|MUSEUM|RESTAURANT|TRANSPORT|MARKET|TEMPLE|ACTIVITY",
          "location_name": "str",
          "latitude": float_or_null,
          "longitude": float_or_null,
          "start_time": "HH:MM_or_empty",
          "end_time": "HH:MM_or_empty",
          "duration_minutes": int,
          "estimated_cost": float,
          "weather_sensitive": bool,
          "indoor": bool,
          "reason": "why this activity",
          "confidence": 0.0_to_1.0
        }}
      ],
      "notes": "day notes"
    }}
  ],
  "reasoning": "overall planning rationale"
}}

Generate days 1 through {n_days}. Use ONLY the places and data provided above.
"""

        try:
            return await self._llm.generate_structured(
                prompt, GeneratedPlan, system=ASSEMBLY_SYSTEM
            )
        except LLMError as exc:
            logger.error("Failed to assemble itinerary: %s", exc)
            return GeneratedPlan(days=[], reasoning=f"Assembly failed: {exc}")
