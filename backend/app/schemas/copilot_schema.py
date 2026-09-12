"""Schemas for copilot, suggestion protocol, contingency, and what-if APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# -- Copilot Chat --

class CopilotRequest(BaseModel):
    """User message to the copilot."""
    message: str = Field(..., min_length=1, max_length=2000)


class CopilotMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    role: str   # user | assistant | system
    content: str
    data: dict = {}
    created_at: datetime


# -- Suggestion Protocol --
# Every AI change = structured proposal with accept/reject/edit

class SuggestedChange(BaseModel):
    """A single AI-proposed change to the itinerary."""
    # add_activity | remove_activity | move_activity | update_activity | swap_activity
    change_type: str
    target_day: int | None = None
    target_activity_id: str | None = None
    proposed_data: dict = Field(default_factory=dict)  # ActivityCreate-like data
    problem: str = ""  # what triggered this suggestion
    reason: str = ""   # why this solution
    impact: str = ""   # budget/time/route impact description
    confidence: float = 0.5


class SuggestionOut(BaseModel):
    """Structured AI proposal with accept/reject."""
    suggestion_id: str  # used to accept/reject
    changes: list[SuggestedChange] = []
    problem: str = ""
    reasoning: str = ""
    impact_summary: str = ""


class SuggestionAction(BaseModel):
    """User response to a suggestion."""
    action: str = Field(..., pattern="^(accept|reject|edit)$")
    edits: dict = Field(default_factory=dict)  # only for action="edit"


class SuggestionActionResponse(BaseModel):
    status: str
    applied_changes: int = 0
    cascade: dict = Field(default_factory=dict)  # budget/route/conflict recalc results


# -- Contingency --

class ContingencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    plan_level: str
    trigger: str
    condition: str
    affected_activity_ids: list = []
    fallback_plan: list = []
    budget_impact: float | None = None
    time_impact_minutes: int | None = None
    confidence: float | None = None
    reason: str = ""
    requires_user_approval: bool = True
    status: str
    created_at: datetime


class ContingencyAction(BaseModel):
    action: str = Field(..., pattern="^(accept|dismiss|activate)$")


# -- What-If Simulation --

class WhatIfRequest(BaseModel):
    """What-if scenario definition."""
    scenario: str = Field(
        ...,
        description=(
            "Scenario type: flight_delay, rain, budget_change, "
            "fewer_travelers, hotel_unavailable, extra_day"
        ),
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Scenario-specific parameters (e.g. delay_hours, new_budget)",
    )


class WhatIfResult(BaseModel):
    scenario: str
    parameters: dict = {}
    impact_chain: list[str] = []
    affected_days: list[int] = []
    affected_activities: list[str] = []
    budget_delta: float = 0.0
    time_delta_minutes: int = 0
    contingency_triggered: list[str] = []
    suggestions: list[SuggestedChange] = []
    reasoning: str = ""
