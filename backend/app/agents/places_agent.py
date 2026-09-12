"""Places Agent module for finding attractions, restaurants, and activities."""

import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for


class PlacesAgent(BaseAgent):
    name: ClassVar[str] = "places"
    description: ClassVar[str] = (
        "Specializes in finding activities, attractions, and dining options."
    )

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 3

    def system_prompt(self) -> str:
        return (
            "You are a places/activities specialist. Find attractions, restaurants, beaches, "
            "temples, markets matching user interests. NEVER invent ratings or costs. "
            "Return activity suggestions with data from search results.\n\n"
            "Provide your final answer using the following JSON schema:\n"
            "{\n"
            '  "activities": [\n'
            "    {\n"
            '      "name": "str",\n'
            '      "category": "str",\n'
            '      "location_name": "str",\n'
            '      "latitude": "float",\n'
            '      "longitude": "float",\n'
            '      "estimated_duration_minutes": "int",\n'
            '      "estimated_cost": "float",\n'
            '      "weather_sensitive": "bool",\n'
            '      "indoor": "bool",\n'
            '      "reason": "str",\n'
            '      "data_source": "str"\n'
            "    }\n"
            "  ],\n"
            '  "reasoning": "str"\n'
            "}"
        )

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("search_places", "find_nearby_places", "geocode_place")

    def _build_user_prompt(self, context: AgentContext) -> str:
        trip_data_str = json.dumps(context.trip_data, indent=2, default=str)
        if len(trip_data_str) > 4000:
            trip_data_str = trip_data_str[:4000] + "... (truncated)"

        prefs_str = json.dumps(context.preferences, indent=2, default=str)
        if len(prefs_str) > 2000:
            prefs_str = prefs_str[:2000] + "... (truncated)"

        return (
            "Find the best places and activities based on the following details:\n\n"
            f"Trip Data:\n{trip_data_str}\n\n"
            f"Preferences:\n{prefs_str}\n\n"
            "Extract the destination coordinates, interest tags from preferences, trip_style, "
            "and num_days to guide your search. Focus on providing real, verified places."
        )
