"""Accommodation Agent module for finding and ranking lodging options."""
import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for

class AccommodationAgent(BaseAgent):
    name: ClassVar[str] = 'accommodation'
    description: ClassVar[str] = 'Specializes in finding and ranking accommodations like hotels and guesthouses.'

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 3

    def system_prompt(self) -> str:
        return """You are an accommodation specialist. Search for hotels/guesthouses. Compare by price, rating, location proximity to activities. NEVER invent prices. Return ranked options.

Provide your final answer using the following JSON schema:
{
  "options": [
    {
      "name": "str",
      "location": "str",
      "price_per_night": "float",
      "currency": "str",
      "rating": "float",
      "source": "str",
      "is_mock": "bool",
      "ranking_reason": "str"
    }
  ],
  "recommendation": "str",
  "reasoning": "str"
}"""

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("search_stays", "geocode_place", "get_exchange_rate")

    def _build_user_prompt(self, context: AgentContext) -> str:
        trip_data_str = json.dumps(context.trip_data, indent=2, default=str)
        if len(trip_data_str) > 4000:
            trip_data_str = trip_data_str[:4000] + "... (truncated)"
            
        prefs_str = json.dumps(context.preferences, indent=2, default=str)
        if len(prefs_str) > 2000:
            prefs_str = prefs_str[:2000] + "... (truncated)"

        prior_results_str = json.dumps(context.prior_results.get('places', {}), indent=2, default=str)
        if len(prior_results_str) > 2000:
            prior_results_str = prior_results_str[:2000] + "... (truncated)"

        return f"""Find optimal accommodation options based on the following details:

Trip Data:
{trip_data_str}

Preferences:
{prefs_str}

Prior Places Data:
{prior_results_str}

Extract destination, dates, num_travelers, and budget allocation for accommodation to execute your search. Use tools to find real options, considering proximity to activities if places data is available."""
