"""Contingency Agent module for planning backups and risk mitigation."""
import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for

class ContingencyAgent(BaseAgent):
    name: ClassVar[str] = 'contingency'
    description: ClassVar[str] = 'Specializes in creating backup plans and handling itinerary disruptions.'

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 2

    def system_prompt(self) -> str:
        return """You are a contingency planning specialist. Generate structured backup plans for identified risks (weather, transport delays, accommodation issues, budget overruns). Each contingency has a trigger condition, affected activities, fallback steps, budget/time impact, and confidence. NEVER invent data — use tool results for alternatives.

Provide your final answer using the following JSON schema:
{
  "contingencies": [
    {
      "plan_level": "B|C|D",
      "trigger": "RAIN|FLIGHT_DELAY|HOTEL_ISSUE|BUDGET_OVERRUN",
      "condition": "str",
      "affected_activity_names": ["str"],
      "fallback_steps": ["str"],
      "budget_impact": "float|null",
      "time_impact_minutes": "int|null",
      "confidence": "float",
      "reason": "str"
    }
  ],
  "reasoning": "str"
}"""

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("search_places", "find_nearby_places", "search_transport", "search_stays")

    def _build_user_prompt(self, context: AgentContext) -> str:
        risks_str = json.dumps(context.prior_results.get('weather_risk', {}), indent=2, default=str)
        if len(risks_str) > 2000:
            risks_str = risks_str[:2000] + "... (truncated)"
            
        itinerary_str = json.dumps(context.trip_data.get('itinerary', {}), indent=2, default=str)
        if len(itinerary_str) > 4000:
            itinerary_str = itinerary_str[:4000] + "... (truncated)"
            
        transport_str = json.dumps(context.prior_results.get('transport', {}), indent=2, default=str)
        if len(transport_str) > 2000:
            transport_str = transport_str[:2000] + "... (truncated)"

        return f"""Develop contingency plans for the following trip:

Weather Risks:
{risks_str}

Itinerary Data:
{itinerary_str}

Transport Data:
{transport_str}

Identify potential failure points (e.g., weather, transport delays) and define clear alternative steps, leveraging tools to find actual backup options."""
