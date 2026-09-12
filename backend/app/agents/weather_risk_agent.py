"""Weather Risk Agent module for assessing weather impacts on the itinerary."""
import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for

class WeatherRiskAgent(BaseAgent):
    name: ClassVar[str] = 'weather_risk'
    description: ClassVar[str] = 'Specializes in analyzing weather forecasts and identifying risks to the itinerary.'

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 2

    def system_prompt(self) -> str:
        return """You are a weather risk analyst. Assess weather forecasts against the itinerary. For rainy days, suggest rescheduling outdoor activities to dry days or finding indoor alternatives. For extreme heat, suggest morning/evening scheduling. NEVER invent weather data — only use forecast results. Clearly separate: live data | forecast | inference | recommendation.

Provide your final answer using the following JSON schema:
{
  "days_at_risk": [
    {
      "day_number": "int",
      "risk": "rain|heat|severe|none",
      "reasons": ["str"],
      "affected_activities": ["str"],
      "suggestions": [
        {
          "type": "reschedule|swap_indoor|split_timing",
          "activity": "str",
          "alternative": "str",
          "reason": "str",
          "confidence": "str"
        }
      ]
    }
  ],
  "overall_risk_level": "str",
  "reasoning": "str"
}"""

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("get_weather", "search_places", "find_nearby_places")

    def _build_user_prompt(self, context: AgentContext) -> str:
        weather_str = json.dumps(context.weather_data, indent=2, default=str)
        if len(weather_str) > 3000:
            weather_str = weather_str[:3000] + "... (truncated)"
            
        itinerary_str = json.dumps(context.trip_data.get('itinerary', {}), indent=2, default=str)
        if len(itinerary_str) > 4000:
            itinerary_str = itinerary_str[:4000] + "... (truncated)"

        return f"""Evaluate the following itinerary for weather risks:

Weather Data:
{weather_str}

Itinerary Data:
{itinerary_str}

Assess the forecast against the daily activities. Pay special attention to weather-sensitive outdoor activities and suggest concrete alternatives or scheduling adjustments."""
