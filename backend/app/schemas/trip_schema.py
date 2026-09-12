"""Trip contracts — the primary user inputs (spec §1)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.itinerary_schema import ItineraryDayOut


class TripBase(BaseModel):
    title: str = Field(default="", max_length=200)
    origin_name: str = Field(default="", max_length=200)
    origin_lat: float | None = Field(default=None, ge=-90, le=90)
    origin_lng: float | None = Field(default=None, ge=-180, le=180)
    destination_name: str = Field(min_length=1, max_length=200)
    destination_lat: float | None = Field(default=None, ge=-90, le=90)
    destination_lng: float | None = Field(default=None, ge=-180, le=180)

    start_date: date
    end_date: date
    num_travelers: int = Field(default=1, ge=1, le=30)

    total_budget: float | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")

    trip_style: str = Field(default="", max_length=50)
    constraints: str = Field(default="", max_length=2000)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def dates_ordered(self) -> TripBase:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TripCreate(TripBase):
    pass


class TripUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    origin_name: str | None = Field(default=None, max_length=200)
    origin_lat: float | None = None
    origin_lng: float | None = None
    destination_name: str | None = Field(default=None, min_length=1, max_length=200)
    destination_lat: float | None = None
    destination_lng: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    num_travelers: int | None = Field(default=None, ge=1, le=30)
    total_budget: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern="^[A-Z]{3}$")
    trip_style: str | None = Field(default=None, max_length=50)
    constraints: str | None = Field(default=None, max_length=2000)
    preferences: dict[str, Any] | None = None
    status: str | None = Field(default=None, pattern="^(draft|planning|confirmed|completed)$")


class TripOut(TripBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    days: list[ItineraryDayOut] = []


class TripListOut(BaseModel):
    items: list[TripOut]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
