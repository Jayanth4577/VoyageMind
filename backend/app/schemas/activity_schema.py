"""Activity contracts — mirrors the spec's structured activity JSON (spec §2B)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"


class ActivityBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="ACTIVITY", max_length=40)
    location_name: str = Field(default="", max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    start_time: str = Field(default="", pattern=f"({TIME_RE})|^$")
    end_time: str = Field(default="", pattern=f"({TIME_RE})|^$")
    duration_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    estimated_cost: float = Field(default=0.0, ge=0)
    weather_sensitive: bool = False
    indoor: bool = False
    notes: str = Field(default="", max_length=1000)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def category_upper(cls, v: str) -> str:
        return v.strip().upper()


class ActivityCreate(ActivityBase):
    day_id: str
    source: str = Field(default="user", pattern="^(user|ai|api)$")
    user_selected: bool = True
    ai_recommended: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)


class ActivityUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    location_name: str | None = Field(default=None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    start_time: str | None = Field(default=None, pattern=f"({TIME_RE})|^$")
    end_time: str | None = Field(default=None, pattern=f"({TIME_RE})|^$")
    duration_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    estimated_cost: float | None = Field(default=None, ge=0)
    weather_sensitive: bool | None = None
    indoor: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)
    meta: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ActivityOut(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    day_id: str
    source: str
    user_selected: bool
    ai_recommended: bool
    confidence: float | None = None
    created_at: datetime
    updated_at: datetime
