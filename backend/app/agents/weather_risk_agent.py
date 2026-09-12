"""Weather Risk Agent module for assessing weather impacts on the itinerary."""

import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for


class WeatherRiskAgent(BaseAgent):
    name: ClassVar[str] = "weather_risk"
    description: ClassVar[str] = (
        "Specializes in analyzing weather forecasts and identifying risks to the itinerary."
    )

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 2

    def system_prompt(self) -> str:
        return (
            "You are a weather risk analyst. Assess weather forecasts against the itinerary. "
            "For rainy days, suggest rescheduling outdoor activities to dry days or finding "
            "indoor alternatives. For extreme heat, suggest morning/evening scheduling. "
            "NEVER invent weather data — only use forecast results. Clearly separate: "
            "live data | forecast | inference | recommendation.\n\n"
            "Provide your final answer using the following JSON schema:\n"
            "{\n"
            '  "days_at_risk": [\n'
            "    {\n"
            '      "day_number": "int",\n'
            '      "risk": "rain|heat|severe|none",\n'
            '      "reasons": ["str"],\n'
            '      "affected_activities": ["str"],\n'
            '      "suggestions": [\n'
            "        {\n"
            '          "type": "reschedule|swap_indoor|split_timing",\n'
            '          "activity": "str",\n'
            '          "alternative": "str",\n'
            '          "reason": "str",\n'
            '          "confidence": "str"\n'
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ],\n"
            '  "overall_risk_level": "str",\n'
            '  "reasoning": "str"\n'
            "}"
        )

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("get_weather", "search_places", "find_nearby_places")

    def _build_user_prompt(self, context: AgentContext) -> str:
        weather_str = json.dumps(context.weather_data, indent=2, default=str)
        if len(weather_str) > 3000:
            weather_str = weather_str[:3000] + "... (truncated)"

        itinerary_str = json.dumps(context.trip_data.get("itinerary", {}), indent=2, default=str)
        if len(itinerary_str) > 4000:
            itinerary_str = itinerary_str[:4000] + "... (truncated)"

        return (
            "Evaluate the following itinerary for weather risks:\n\n"
            f"Weather Data:\n{weather_str}\n\n"
            f"Itinerary Data:\n{itinerary_str}\n\n"
            "Assess the forecast against the daily activities. Pay special attention "
            "to weather-sensitive outdoor activities and suggest concrete alternatives "
            "or scheduling adjustments."
        )
