"""Budget contracts. Arithmetic lives in BudgetService (Phase 2) — schemas only."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

BUDGET_CATEGORIES = (
    "transport",
    "accommodation",
    "food",
    "activities",
    "local_transport",
    "buffer",
)


class BudgetItemCreate(BaseModel):
    category: str = Field(pattern="^(" + "|".join(BUDGET_CATEGORIES) + ")$")
    label: str = Field(default="", max_length=200)
    amount: float = Field(ge=0)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")
    source_ref: str = Field(default="manual", max_length=80)


class BudgetItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    category: str
    label: str
    amount: float
    currency: str
    source_ref: str
    created_at: datetime


class BudgetSummary(BaseModel):
    """Deterministic summary produced by BudgetService (spec §7)."""

    trip_id: str
    currency: str
    total_budget: float | None
    spent: float
    remaining: float | None
    by_category: dict[str, float]
    # under | near | over | unknown (no budget set)
    state: str
