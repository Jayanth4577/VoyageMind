"""Master Agent for intent parsing and delegation."""

from pydantic import BaseModel, Field

from app.agents.context import AgentContext, AgentResult
from app.core.logging import get_logger
from app.llm import LLMError, get_llm_provider

logger = get_logger(__name__)


class IntentSchema(BaseModel):
    intent: str = Field(
        description=(
            "The classified intent: generate, optimize_route, optimize_budget, "
            "check_weather, recommend"
        )
    )
    reasoning: str = Field(description="Reasoning for the chosen intent")


class MasterAgent:
    """Intent understanding + delegation to specialist agents."""

    def __init__(self, *, llm=None):
        self._llm = llm or get_llm_provider()

    async def run(self, context: AgentContext) -> AgentResult:
        """Parse intent and delegate to appropriate agents."""
        logger.info(f"MasterAgent processing request for trip {context.trip_id}")

        intent = await self._parse_intent(context)
        logger.info(f"Parsed intent: {intent}")

        if intent == "generate":
            from app.agents.planner_agent import PlannerAgent

            planner = PlannerAgent(llm=self._llm)
            return await planner.run(context)
        elif intent == "optimize_route":
            from app.agents.route_agent import RouteAgent

            agent = RouteAgent(llm=self._llm)
            return await agent.run(context)
        elif intent == "optimize_budget":
            from app.agents.budget_agent import BudgetAgent

            agent = BudgetAgent(llm=self._llm)
            return await agent.run(context)
        elif intent == "check_weather":
            from app.agents.weather_risk_agent import WeatherRiskAgent

            agent = WeatherRiskAgent(llm=self._llm)
            return await agent.run(context)
        elif intent == "recommend":
            from app.agents.places_agent import PlacesAgent

            agent = PlacesAgent(llm=self._llm)
            return await agent.run(context)
        else:
            return AgentResult(
                agent_name="MasterAgent",
                status="failed",
                data={},
                tool_calls=[],
                reasoning=f"Unknown intent: {intent}",
                confidence=0.0,
            )

    async def _parse_intent(self, context: AgentContext) -> str:
        """Use LLM to classify intent from user request."""
        request = context.request
        if not request:
            return "generate"

        prompt = f"""
        Given the user request, classify the intent into one of these categories:
        - generate: creating or generating a full travel plan/itinerary
        - optimize_route: optimizing travel routes, rearranging activities for better logistics
        - optimize_budget: reducing costs, checking budget limits, finding cheaper alternatives
        - check_weather: checking for weather conflicts or risks
        - recommend: recommending places, restaurants, or specific activities without full planning

        Request: "{request}"
        """

        try:
            result = await self._llm.generate_structured(prompt, IntentSchema)
            intent = result.intent
            if intent not in [
                "generate",
                "optimize_route",
                "optimize_budget",
                "check_weather",
                "recommend",
            ]:
                return "generate"
            return intent
        except LLMError as e:
            logger.error(f"Failed to parse intent, defaulting to generate. Error: {e}")
            return "generate"
