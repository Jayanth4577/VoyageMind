"""BaseAgent — the orchestrator loop shared by every specialist agent.

Pattern:
    1. Build a context prompt from ``AgentContext``
    2. Call the LLM with system prompt + context + available tool schemas
    3. If the LLM requests tool calls → execute each, collect results, feed back
    4. Repeat 2–3 up to ``max_iterations``
    5. Parse the LLM's final structured output
    6. Return ``AgentResult`` with data + tool trace + reasoning

The loop is provider-agnostic: the LLM returns a JSON ``LLMStepResponse``
which may contain tool call requests (the framework executes them) or a final
answer.  This avoids depending on native function-calling support from every
provider.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import ClassVar

from app.agents.context import (
    AgentContext,
    AgentResult,
    LLMStepResponse,
    ToolDefinition,
    ToolTrace,
)
from app.agents.tools import execute_tool
from app.core.logging import get_logger
from app.llm import LLMError, get_llm_provider
from app.llm.provider import LLMProvider

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base for all VoyageMind agents."""

    name: ClassVar[str] = "base"
    description: ClassVar[str] = ""
    max_iterations: int = 5

    def __init__(self, *, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    # -- Subclass hooks ------------------------------------------------------

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt that defines this agent's persona and rules."""

    @abstractmethod
    def available_tools(self) -> list[ToolDefinition]:
        """Return the tool definitions this agent may use."""

    @abstractmethod
    def _build_user_prompt(self, context: AgentContext) -> str:
        """Build the user-facing prompt from the agent context."""

    # -- Main orchestrator loop ----------------------------------------------

    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent's reasoning loop.

        Returns an ``AgentResult`` with structured data, tool trace, and reasoning.
        The loop tolerates LLM failures and tool failures — it degrades
        gracefully and returns whatever partial data it has.
        """
        all_traces: list[ToolTrace] = []
        tools_json = [t.model_dump() for t in self.available_tools()]

        user_prompt = self._build_user_prompt(context)
        conversation: list[dict] = []

        try:
            for iteration in range(self.max_iterations):
                step_prompt = self._build_step_prompt(
                    user_prompt, tools_json, conversation, iteration
                )
                raw = await self.llm.generate(
                    step_prompt,
                    system=self.system_prompt(),
                    temperature=0.3,
                )

                step = self._parse_step(raw)

                if step.tool_calls:
                    tool_results = []
                    for tc in step.tool_calls:
                        trace = await execute_tool(tc.tool, tc.arguments)
                        all_traces.append(trace)
                        tool_results.append(
                            {"tool": tc.tool, "result": trace.result}
                        )
                    conversation.append(
                        {"role": "assistant", "tool_calls": [tc.model_dump() for tc in step.tool_calls]}
                    )
                    conversation.append(
                        {"role": "tool_results", "results": tool_results}
                    )
                    continue

                if step.done or iteration == self.max_iterations - 1:
                    return AgentResult(
                        agent_name=self.name,
                        status="ok",
                        data=step.final_answer,
                        tool_calls=all_traces,
                        reasoning=step.reasoning,
                    )
        except LLMError as exc:
            logger.warning("agent %s LLM error: %s", self.name, exc)
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={"error": str(exc)},
                tool_calls=all_traces,
                reasoning=f"LLM error: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("agent %s unexpected error: %s", self.name, exc)
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={"error": str(exc)},
                tool_calls=all_traces,
                reasoning=f"Unexpected error: {exc}",
            )

        # Fallback if loop exits without a final answer
        return AgentResult(
            agent_name=self.name,
            status="partial",
            data={},
            tool_calls=all_traces,
            reasoning="Reached max iterations without a final answer",
        )

    # -- Prompt construction -------------------------------------------------

    def _build_step_prompt(
        self,
        user_prompt: str,
        tools_json: list[dict],
        conversation: list[dict],
        iteration: int,
    ) -> str:
        """Assemble the full prompt for one LLM call."""
        parts = [user_prompt]

        if tools_json:
            parts.append(
                "\n\n## Available Tools\n"
                "You may request tool calls by including them in your JSON response.\n"
                f"```json\n{json.dumps(tools_json, indent=2)}\n```"
            )

        if conversation:
            parts.append("\n\n## Conversation So Far")
            for msg in conversation:
                role = msg.get("role", "unknown")
                if role == "tool_results":
                    for r in msg.get("results", []):
                        result_str = json.dumps(r.get("result", {}), indent=2, default=str)
                        # Truncate very large results to avoid context overflow
                        if len(result_str) > 3000:
                            result_str = result_str[:3000] + "\n... (truncated)"
                        parts.append(f"\n### Tool Result: {r.get('tool')}\n```json\n{result_str}\n```")
                elif role == "assistant":
                    calls = msg.get("tool_calls", [])
                    parts.append(
                        f"\n### Your Previous Tool Requests\n```json\n{json.dumps(calls, indent=2)}\n```"
                    )

        remaining = self.max_iterations - iteration - 1
        parts.append(
            f"\n\n## Instructions\n"
            f"You have {remaining} iteration(s) remaining. "
            "Respond with a JSON object following this schema:\n"
            "```json\n"
            '{\n'
            '  "done": false,\n'
            '  "tool_calls": [{"tool": "tool_name", "arguments": {...}}],\n'
            '  "final_answer": {},\n'
            '  "reasoning": ""\n'
            '}\n'
            "```\n"
            "Set `done: true` when you have enough information to provide your "
            "final structured answer. Tool calls and final answer are mutually "
            "exclusive — either request tools OR set done=true with your answer."
        )

        return "\n".join(parts)

    @staticmethod
    def _parse_step(raw: str) -> LLMStepResponse:
        """Parse the LLM's JSON response, tolerating markdown fences and malformed output."""
        try:
            data = LLMProvider._extract_json(raw)
            return LLMStepResponse.model_validate(data)
        except (LLMError, Exception):
            # If the LLM returned something unparseable, treat it as a final answer
            # with the raw text as reasoning
            return LLMStepResponse(
                done=True,
                final_answer={},
                reasoning=raw[:2000] if raw else "Empty LLM response",
            )
