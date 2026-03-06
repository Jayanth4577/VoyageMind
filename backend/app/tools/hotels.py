"""Hotels tool — fetches hotel options from API or mock data.

Implements the tool JSON schema contract required by VoyageMind agents.
All external calls are idempotent and cached upstream.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

MOCK_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "mock_hotels.json"

# Tool schema for Nova structured tool calling
HOTELS_TOOL_SCHEMA: dict[str, Any] = {
    "toolSpec": {
        "name": "search_hotels",
        "description": "Search for available hotels at a destination within a price range.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City or area name"},
                    "check_in": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "check_out": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "guests": {"type": "integer", "description": "Number of guests"},
                    "max_price": {"type": "number", "description": "Max price per night in USD"},
                },
                "required": ["destination", "check_in", "check_out"],
            }
        },
    }
}


class HotelsTool:
    """Searches for hotels — uses RapidAPI in production, mock data locally."""

    async def search(
        self,
        destination: str,
        check_in: str,
        check_out: str,
        guests: int = 2,
        max_price: float | None = None,
    ) -> list[dict[str, Any]]:
        settings = get_settings()

        if settings.mock_mode:
            return self._search_mock(destination, max_price)

        return await self._search_api(destination, check_in, check_out, guests, max_price)

    # ------------------------------------------------------------------
    # Mock implementation
    # ------------------------------------------------------------------

    def _search_mock(self, destination: str, max_price: float | None) -> list[dict[str, Any]]:
        """Return hotels from the local mock JSON dataset."""
        if not MOCK_DATA_PATH.exists():
            logger.warning("Mock hotel data not found at %s", MOCK_DATA_PATH)
            return []

        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            all_hotels: list[dict[str, Any]] = json.load(f)

        dest_lower = destination.lower()
        results = [
            h for h in all_hotels
            if dest_lower in h.get("city", "").lower() or dest_lower in h.get("destination", "").lower()
        ]

        if max_price is not None:
            results = [h for h in results if h.get("price_per_night", 0) <= max_price * 1.2]

        logger.info("Mock hotels: %d results for %s (max $%s)", len(results), destination, max_price)
        return results

    # ------------------------------------------------------------------
    # Live API implementation (RapidAPI / Amadeus)
    # ------------------------------------------------------------------

    async def _search_api(
        self,
        destination: str,
        check_in: str,
        check_out: str,
        guests: int,
        max_price: float | None,
    ) -> list[dict[str, Any]]:
        """Call an external hotel search API."""
        import httpx

        settings = get_settings()
        url = "https://hotels4.p.rapidapi.com/locations/v3/search"
        headers = {
            "X-RapidAPI-Key": settings.rapidapi_key,
            "X-RapidAPI-Host": "hotels4.p.rapidapi.com",
        }
        params = {"q": destination, "locale": "en_US"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        entities = data.get("sr", [])
        hotels = []
        for entity in entities:
            if entity.get("type") == "HOTEL":
                hotels.append({
                    "name": entity.get("regionNames", {}).get("fullName", "Unknown"),
                    "city": destination,
                    "latitude": entity.get("coordinates", {}).get("lat", 0),
                    "longitude": entity.get("coordinates", {}).get("long", 0),
                    "price_per_night": 0,
                    "rating": 0,
                    "amenities": [],
                })

        logger.info("API hotels: %d results for %s", len(hotels), destination)
        return hotels