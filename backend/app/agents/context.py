"""Shared data structures for the agent framework (spec §14, §15).

AgentContext carries the trip state into every agent run; AgentResult carries
structured output + tool trace back out.  All inter-agent communication uses
these Pydantic models so the data is always validated and serialisable.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    """JSON-schema definition for a tool the LLM can request."""

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A single tool invocation request from the LLM."""

    tool: str
    arguments: dict = Field(default_factory=dict)


class ToolTrace(BaseModel):
    """Audit record for one tool call execution."""

    tool: str
    arguments: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None


class AgentContext(BaseModel):
    """Everything an agent needs to reason about a trip."""

    trip_id: str
    trip_data: dict = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)
    weather_data: dict | None = None
    route_data: dict | None = None
    budget_summary: dict | None = None
    prior_results: dict = Field(default_factory=dict)
    request: str = ""


class AgentResult(BaseModel):
    """Structured output from a single agent run."""

    agent_name: str
    status: str = "ok"  # ok | error | partial
    data: dict = Field(default_factory=dict)
    tool_calls: list[ToolTrace] = Field(default_factory=list)
    reasoning: str = ""
    confidence: float | None = None


class LLMStepResponse(BaseModel):
    """What the LLM returns at each step of the orchestrator loop.

    If ``tool_calls`` is non-empty the framework executes those tools and feeds
    results back.  When the LLM sets ``done=True`` the framework reads
    ``final_answer`` and ``reasoning``.
    """

    done: bool = False
    tool_calls: list[ToolCall] = Field(default_factory=list)
    final_answer: dict = Field(default_factory=dict)
    reasoning: str = ""
