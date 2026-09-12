"""Itinerary days + activities — the structured heart of the workspace (spec §2B, §15)."""

from __future__ import annotations

from datetime import date as _date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class ItineraryDay(Base, IdMixin, TimestampMixin):
    __tablename__ = "itinerary_days"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    day_number: Mapped[int] = mapped_column(Integer)
    # aliased import: the field name `date` would shadow the datetime type here
    date: Mapped[_date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(String(2000), default="")

    trip: Mapped[Trip] = relationship(back_populates="days")  # noqa: F821
    activities: Mapped[list[Activity]] = relationship(
        back_populates="day",
        cascade="all, delete-orphan",
        order_by="Activity.position, Activity.start_time",
    )


class Activity(Base, IdMixin, TimestampMixin):
    __tablename__ = "activities"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    day_id: Mapped[str] = mapped_column(ForeignKey("itinerary_days.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    # BEACH, MUSEUM, RESTAURANT, TRANSPORT, FREE_TIME, ... free enum for prototype
    category: Mapped[str] = mapped_column(String(40), default="ACTIVITY")
    location_name: Mapped[str] = mapped_column(String(200), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # "HH:MM" 24h strings per the spec's activity JSON contract
    start_time: Mapped[str] = mapped_column(String(5), default="")
    end_time: Mapped[str] = mapped_column(String(5), default="")
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    weather_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    indoor: Mapped[bool] = mapped_column(Boolean, default=False)

    # user | ai | api (spec: user-created, AI-recommended, API-retrieved)
    source: Mapped[str] = mapped_column(String(10), default="user")
    user_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str] = mapped_column(String(1000), default="")
    # Manual ordering within a day (drag & drop); 0 = first
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Provider-agnostic extras (place id, price source, etc.)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    day: Mapped[ItineraryDay] = relationship(back_populates="activities")
