"""Transport Agent module for finding and ranking travel options."""

import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for


class TransportAgent(BaseAgent):
    name: ClassVar[str] = "transport"
    description: ClassVar[str] = (
        "Specializes in finding and ranking transport options like flights, trains, and buses."
    )

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 3

    def system_prompt(self) -> str:
        return (
            "You are a transport specialist. Search for flights/trains/buses between "
            "origin and destination. Compare options by price, duration, and convenience. "
            "NEVER invent prices or times — only use data from search results. "
            "Return ranked options with reasoning.\n\n"
            "Provide your final answer using the following JSON schema:\n"
            "{\n"
            '  "options": [\n'
            "    {\n"
            '      "kind": "flight|train|bus",\n'
            '      "provider": "str",\n'
            '      "origin": "str",\n'
            '      "destination": "str",\n'
            '      "departure": "str",\n'
            '      "arrival": "str",\n'
            '      "duration_minutes": "int",\n'
            '      "price": "float",\n'
            '      "currency": "str",\n'
            '      "source": "str",\n'
            '      "is_mock": "bool",\n'
            '      "ranking_reason": "str"\n'
            "    }\n"
            "  ],\n"
            '  "recommendation": "str",\n'
            '  "reasoning": "str"\n'
            "}"
        )

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for("search_transport", "get_exchange_rate")

    def _build_user_prompt(self, context: AgentContext) -> str:
        trip_data_str = json.dumps(context.trip_data, indent=2, default=str)
        if len(trip_data_str) > 4000:
            trip_data_str = trip_data_str[:4000] + "... (truncated)"

        prefs_str = json.dumps(context.preferences, indent=2, default=str)
        if len(prefs_str) > 2000:
            prefs_str = prefs_str[:2000] + "... (truncated)"

        return (
            "Find optimal transport options based on the following details:\n\n"
            f"Trip Data:\n{trip_data_str}\n\n"
            f"Preferences:\n{prefs_str}\n\n"
            "Please extract the origin, destination, start_date, and transport style "
            "preferences to execute your search. Use tools to find real options, compare "
            "them, and return the best ones."
        )
