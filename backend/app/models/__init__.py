"""All ORM models. Importing this package registers every mapper."""

from __future__ import annotations

from app.models.budget import BudgetItem
from app.models.contingency import Contingency
from app.models.event import CopilotMessage, TripEvent
from app.models.itinerary import Activity, ItineraryDay
from app.models.recommendation import Recommendation
from app.models.transport import Accommodation, TransportOption
from app.models.trip import Trip, TripPreference
from app.models.user import User
from app.models.weather import WeatherSnapshot

__all__ = [
    "Accommodation",
    "Activity",
    "BudgetItem",
    "Contingency",
    "CopilotMessage",
    "ItineraryDay",
    "Recommendation",
    "TransportOption",
    "Trip",
    "TripEvent",
    "TripPreference",
    "User",
    "WeatherSnapshot",
]
