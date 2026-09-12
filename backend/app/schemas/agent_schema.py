"""Schemas for agent API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    """Optional preferences override for plan generation."""

    preferences: dict = Field(default_factory=dict)
    constraints: str = ""


class GeneratedActivity(BaseModel):
    name: str
    category: str = "ACTIVITY"
    location_name: str = ""
    latitude: float | None = None
    longitude: float | None = None
    start_time: str = ""
    end_time: str = ""
    duration_minutes: int = 60
    estimated_cost: float = 0.0
    weather_sensitive: bool = False
    indoor: bool = False
    reason: str = ""
    confidence: float = 0.5


class GeneratedDay(BaseModel):
    day_number: int
    title: str = ""
    activities: list[GeneratedActivity] = []
    notes: str = ""


class GeneratedPlan(BaseModel):
    days: list[GeneratedDay] = []
    reasoning: str = ""


class GenerateResponse(BaseModel):
    trip_id: str
    status: str
    plan: GeneratedPlan | None = None
    transport_options: list[dict] = []
    accommodation_options: list[dict] = []
    weather_summary: dict = {}
    budget_estimate: dict = {}
    risks: list[dict] = []
    contingencies: list[dict] = []
    tool_calls_count: int = 0
    reasoning: str = ""


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    name: str
    category: str
    latitude: float | None = None
    longitude: float | None = None
    estimated_cost: float | None = None
    estimated_duration_minutes: int | None = None
    rating: float | None = None
    weather_suitability: str = ""
    reason: str = ""
    data_source: str = ""
    confidence: float | None = None
    status: str
    created_at: datetime
