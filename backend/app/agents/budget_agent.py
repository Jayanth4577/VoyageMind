"""Budget Agent module for tracking expenses and suggesting savings."""

import json
from typing import ClassVar

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, ToolDefinition
from app.agents.tools import tool_definitions_for


class BudgetAgent(BaseAgent):
    name: ClassVar[str] = "budget"
    description: ClassVar[str] = "Specializes in budget optimization and finding cost savings."

    def __init__(self, *, llm=None):
        super().__init__(llm=llm)
        self.max_iterations = 3

    def system_prompt(self) -> str:
        return (
            "You are a budget optimization specialist. Analyse the trip's spending "
            "against the total budget. Identify categories over budget. Search for cheaper "
            "alternatives if needed. NEVER invent prices — only use data from search results "
            "or existing budget items. Suggest concrete savings with exact amounts from "
            "real data.\n\n"
            "Provide your final answer using the following JSON schema:\n"
            "{\n"
            '  "status": "on_track|over_budget|near_budget",\n'
            '  "total_budget": "float",\n'
            '  "spent": "float",\n'
            '  "remaining": "float",\n'
            '  "savings_suggestions": [\n'
            "    {\n"
            '      "category": "str",\n'
            '      "current_item": "str",\n'
            '      "alternative": "str",\n'
            '      "saving_amount": "float",\n'
            '      "rationale": "str"\n'
            "    }\n"
            "  ],\n"
            '  "reasoning": "str"\n'
            "}"
        )

    def available_tools(self) -> list[ToolDefinition]:
        return tool_definitions_for(
            "search_stays", "search_transport", "search_places", "get_exchange_rate"
        )

    def _build_user_prompt(self, context: AgentContext) -> str:
        budget_str = json.dumps(context.budget_summary, indent=2, default=str)
        if len(budget_str) > 4000:
            budget_str = budget_str[:4000] + "... (truncated)"

        prior_results_str = json.dumps(context.prior_results, indent=2, default=str)
        if len(prior_results_str) > 4000:
            prior_results_str = prior_results_str[:4000] + "... (truncated)"

        return (
            "Analyze the trip budget and propose optimizations:\n\n"
            f"Budget Summary:\n{budget_str}\n\n"
            f"Prior Results / Current Bookings:\n{prior_results_str}\n\n"
            "Evaluate the total spending by category against the total budget. "
            "If any category is over budget, search for and suggest realistic, "
            "cheaper alternatives."
        )
