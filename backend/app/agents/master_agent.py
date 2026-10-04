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
        """Use LLM to classify intent from user request, with a keyword fallback."""
        request = context.request
        if not request:
            return "generate"

        # Keyword heuristic first — fast, deterministic, and catches the common
        # phrasings the LLM sometimes mis-routes (e.g. "suggest some places"
        # landing on generate and replying with a whole itinerary).
        lowered = request.lower()
        suggest_words = (
            "suggest", "recommend", "places to", "places near",
            "things to do", "nearby", "restaurants", "attractions",
        )
        plan_words = ("itinerary", "plan my", "full plan", "generate")
        if any(k in lowered for k in suggest_words) and not any(
            k in lowered for k in plan_words
        ):
            return "recommend"
        budget_words = ("budget", "cheaper", "reduce cost", "too expensive", "save money")
        if any(k in lowered for k in budget_words):
            return "optimize_budget"
        if any(k in lowered for k in ("rain", "weather", "forecast")):
            return "check_weather"
        if any(k in lowered for k in ("realistic", "reorder", "rearrange", "route", "travel time")):
            return "optimize_route"

        prompt = f"""
        Given the user request, classify the intent into one of these categories:
        - generate: creating or regenerating a full travel plan/itinerary
        - optimize_route: optimizing travel routes, rearranging activities for better logistics
        - optimize_budget: reducing costs, checking budget limits, finding cheaper alternatives
        - check_weather: checking for weather conflicts or risks
        - recommend: recommending places, restaurants, or specific activities WITHOUT full planning

        Examples:
        "plan a 5 day trip" -> generate
        "hi" -> generate
        "suggest some places to visit" -> recommend
        "recommend places near my hotel" -> recommend
        "what can I do in the evening?" -> recommend
        "make this cheaper" -> optimize_budget
        "will it rain on my trip?" -> check_weather
        "the schedule looks impossible" -> optimize_route

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
