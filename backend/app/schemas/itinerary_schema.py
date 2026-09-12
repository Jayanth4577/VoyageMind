"""Itinerary day contracts."""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.activity_schema import ActivityOut


class ItineraryDayBase(BaseModel):
    day_number: int = Field(ge=1)
    # aliased import: the field name `date` would shadow the datetime type here
    date: _date | None = None
    title: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)


class ItineraryDayOut(ItineraryDayBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    activities: list[ActivityOut] = []
    created_at: datetime
    updated_at: datetime


class ItineraryOut(BaseModel):
    trip_id: str
    days: list[ItineraryDayOut]
