"""Route Agent module for optimizing daily itineraries and travel times."""

import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for


class RouteAgent(BaseAgent):
    name: ClassVar[str] = "route"
    description: ClassVar[str] = (
        "Specializes in optimizing the order of activities to minimize travel time."
    )

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 2

    def system_prompt(self) -> str:
        return (
            "You are a route optimization specialist. Given activities with coordinates, "
            "evaluate travel times and suggest the most efficient visiting order per day. "
            "Report time savings. NEVER invent travel times — only use routing data.\n\n"
            "Provide your final answer using the following JSON schema:\n"
            "{\n"
            '  "days": [\n'
            "    {\n"
            '      "day_number": "int",\n'
            '      "suggested_order": ["str"],\n'
            '      "current_duration_minutes": "int",\n'
            '      "optimized_duration_minutes": "int",\n'
            '      "saved_minutes": "int",\n'
            '      "explanation": "str"\n'
            "    }\n"
            "  ],\n"
            '  "total_saved_minutes": "int",\n'
            '  "reasoning": "str"\n'
            "}"
        )

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("calculate_route", "optimize_route")

    def _build_user_prompt(self, context: AgentContext) -> str:
        activities_str = json.dumps(context.prior_results.get("places", {}), indent=2, default=str)
        if not context.prior_results.get("places"):
            activities_str = json.dumps(
                context.trip_data.get("itinerary", {}), indent=2, default=str
            )

        if len(activities_str) > 4000:
            activities_str = activities_str[:4000] + "... (truncated)"

        return (
            "Optimize the daily route for the following activities:\n\n"
            f"Activities/Itinerary Data:\n{activities_str}\n\n"
            "Extract activities per day along with their coordinates. "
            "Use your tools to determine the optimal visiting order to minimize travel time."
        )
