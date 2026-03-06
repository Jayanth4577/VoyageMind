"""Accommodation Agent for VoyageMind.

Optimizes hotel choices based on:
- Location clustering (proximity to attractions)
- Distance to key attractions
- Budget constraints
- Traveler count

Uses the ReAct (Reasoning + Acting) pattern with Amazon Nova 2 Pro.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.bedrock_client import BedrockClient
from app.core.cache import cache_result, get_cached_result
from app.core.prompt_templates import ACCOMMODATION_PROMPT
from app.models.schemas import (
    AccommodationRequest,
    AccommodationResult,
    HotelOption,
)
from app.tools.hotels import HotelsTool
from app.tools.maps import MapsTool

logger = logging.getLogger(__name__)


class AccommodationAgent:
    """
    Sub-agent responsible for optimizing hotel selections.

    Evaluates hotel options considering:
    - Budget per night (total budget / nights / rooms)
    - Proximity to planned attractions (geo-clustering)
    - Guest ratings and amenities
    - Location clustering for walkability
    """

    def __init__(self, bedrock_client: BedrockClient):
        self.bedrock_client = bedrock_client
        self.hotels_tool = HotelsTool()
        self.maps_tool = MapsTool()

    async def run(self, request: AccommodationRequest) -> AccommodationResult:
        """
        Execute the accommodation agent using the ReAct pattern.

        Steps:
          1. Thought  — Analyze budget constraints
          2. Action   — Fetch available hotels
          3. Observe  — Process hotel results
          4. Action   — Compute distances to attractions
          5. Thought  — Score and rank hotels
          6. Action   — Invoke Nova 2 Pro for final reasoning
          7. Result   — Return ranked accommodation options
        """
        logger.info(
            "AccommodationAgent started | destination=%s budget=%.2f travelers=%d",
            request.destination,
            request.budget,
            request.travelers,
        )

        reasoning_steps: list[dict[str, Any]] = []

        # ── Step 1: Thought — budget analysis ────────────────────────
        nights = (request.check_out - request.check_in).days
        rooms = max(1, (request.travelers + 1) // 2)
        budget_per_night = request.budget / max(nights, 1) / rooms

        reasoning_steps.append({
            "step": "thought",
            "content": (
                f"Trip is {nights} night(s), need {rooms} room(s). "
                f"Budget per room per night: ${budget_per_night:.2f}"
            ),
        })
        logger.info("Budget analysis: %d nights, %d rooms, $%.2f/night", nights, rooms, budget_per_night)

        # ── Step 2: Action — fetch hotels (cached) ───────────────────
        cache_key = (
            f"hotels:{request.destination}:{request.check_in}"
            f":{request.check_out}:{request.travelers}"
        )
        cached = await get_cached_result(cache_key)

        if cached:
            hotels_raw = cached
            reasoning_steps.append({
                "step": "action",
                "tool": "hotels",
                "content": "Retrieved hotels from cache.",
            })
        else:
            hotels_raw = await self.hotels_tool.search(
                destination=request.destination,
                check_in=str(request.check_in),
                check_out=str(request.check_out),
                guests=request.travelers,
                max_price=budget_per_night,
            )
            await cache_result(cache_key, hotels_raw)
            reasoning_steps.append({
                "step": "action",
                "tool": "hotels",
                "content": f"Fetched {len(hotels_raw)} hotel options from API.",
            })

        logger.info("Hotels retrieved: %d options", len(hotels_raw))

        # Early exit if nothing found
        if not hotels_raw:
            return AccommodationResult(
                hotels=[],
                reasoning="No hotels found within the given budget and dates.",
                reasoning_steps=reasoning_steps,
            )

        # ── Step 3: Observation — summarize hotel data ───────────────
        prices = [h["price_per_night"] for h in hotels_raw]
        reasoning_steps.append({
            "step": "observation",
            "content": (
                f"Received {len(hotels_raw)} hotels. "
                f"Price range: ${min(prices):.0f}–${max(prices):.0f}/night."
            ),
        })

        # ── Step 4: Action — distances to attractions ────────────────
        attractions = await self.maps_tool.get_nearby_attractions(
            destination=request.destination,
            latitude=request.latitude,
            longitude=request.longitude,
        )

        for hotel in hotels_raw:
            hotel["attraction_distances"] = await self.maps_tool.compute_distances(
                origin_lat=hotel.get("latitude", 0),
                origin_lon=hotel.get("longitude", 0),
                attractions=attractions,
            )
            hotel["avg_distance_km"] = (
                sum(d["distance_km"] for d in hotel["attraction_distances"])
                / max(len(hotel["attraction_distances"]), 1)
            )

        reasoning_steps.append({
            "step": "action",
            "tool": "maps",
            "content": (
                f"Computed distances to {len(attractions)} nearby "
                f"attractions for each hotel."
            ),
        })

        # ── Step 5: Thought — score & rank ───────────────────────────
        scored = self._score_hotels(hotels_raw, budget_per_night)
        scored.sort(key=lambda h: h["score"], reverse=True)
        top_hotels = scored[:5]

        reasoning_steps.append({
            "step": "thought",
            "content": (
                f"Scored {len(scored)} hotels on budget fit, distance, and rating. "
                f"Top pick: {top_hotels[0]['name']} "
                f"(score: {top_hotels[0]['score']:.2f})."
            ),
        })

        # ── Step 6: Action — Nova reasoning ──────────────────────────
        prompt = ACCOMMODATION_PROMPT.format(
            destination=request.destination,
            check_in=request.check_in,
            check_out=request.check_out,
            nights=nights,
            rooms=rooms,
            budget_per_night=budget_per_night,
            travelers=request.travelers,
            hotels_json=json.dumps(top_hotels, indent=2, default=str),
            attractions_json=json.dumps(attractions, indent=2, default=str),
        )

        nova_response = await self.bedrock_client.invoke(
            prompt=prompt,
            system=(
                "You are VoyageMind's Accommodation Agent. "
                "Recommend the best hotel based on budget, location, and rating. "
                "Return structured JSON only."
            ),
        )

        reasoning_steps.append({
            "step": "action",
            "tool": "nova",
            "content": "Invoked Nova 2 Pro for final accommodation reasoning.",
        })

        # ── Step 7: Build result ─────────────────────────────────────
        recommended = self._parse_nova_response(nova_response, top_hotels)

        reasoning_steps.append({
            "step": "result",
            "content": (
                f"Recommended {len(recommended)} hotel(s). "
                f"Primary: {recommended[0].name if recommended else 'N/A'}."
            ),
        })

        logger.info(
            "AccommodationAgent completed | recommended=%d hotels",
            len(recommended),
        )

        return AccommodationResult(
            hotels=recommended,
            reasoning=nova_response,
            reasoning_steps=reasoning_steps,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_hotels(
        self,
        hotels: list[dict[str, Any]],
        budget_per_night: float,
    ) -> list[dict[str, Any]]:
        """
        Score each hotel on a 0–1 scale combining:
          - Budget fit  (40 %) — How close the price is to budget without exceeding it.
          - Distance    (35 %) — Average distance to attractions (lower is better).
          - Rating      (25 %) — Guest rating normalized to 0–1.
        """
        max_distance = (
            max((h.get("avg_distance_km", 1) for h in hotels), default=1) or 1
        )

        for hotel in hotels:
            price = hotel.get("price_per_night", 0)

            # Budget fit
            if price <= budget_per_night:
                budget_score = 1.0 - (budget_per_night - price) / max(budget_per_night, 1) * 0.3
            else:
                budget_score = max(
                    0.0, 1.0 - (price - budget_per_night) / max(budget_per_night, 1)
                )

            # Distance (closer = higher score)
            distance_score = 1.0 - hotel.get("avg_distance_km", max_distance) / max_distance

            # Rating
            rating_score = hotel.get("rating", 3.0) / 5.0

            hotel["score"] = round(
                0.40 * budget_score + 0.35 * distance_score + 0.25 * rating_score,
                4,
            )

        return hotels

    # ------------------------------------------------------------------
    # Nova response parsing
    # ------------------------------------------------------------------

    def _parse_nova_response(
        self,
        response: str,
        fallback_hotels: list[dict[str, Any]],
    ) -> list[HotelOption]:
        """Parse Nova's JSON response into HotelOption models, with fallback."""
        try:
            data = json.loads(response)
            recommendations = (
                data
                if isinstance(data, list)
                else data.get("recommendations", data.get("hotels", []))
            )
            return [
                HotelOption(
                    name=h.get("name", "Unknown"),
                    price_per_night=h.get("price_per_night", 0),
                    rating=h.get("rating", 0),
                    distance_to_center_km=h.get(
                        "avg_distance_km", h.get("distance_to_center_km", 0)
                    ),
                    latitude=h.get("latitude", 0),
                    longitude=h.get("longitude", 0),
                    amenities=h.get("amenities", []),
                    reason=h.get("reason", ""),
                )
                for h in recommendations[:3]
            ]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse Nova response, using scored fallback: %s", exc)
            return [
                HotelOption(
                    name=h["name"],
                    price_per_night=h["price_per_night"],
                    rating=h.get("rating", 0),
                    distance_to_center_km=h.get("avg_distance_km", 0),
                    latitude=h.get("latitude", 0),
                    longitude=h.get("longitude", 0),
                    amenities=h.get("amenities", []),
                    reason=f"Score: {h.get('score', 0):.2f}",
                )
                for h in fallback_hotels[:3]
            ]