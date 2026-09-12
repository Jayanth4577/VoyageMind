"""Trip aggregate: core trip inputs + per-traveler group preferences."""
from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class Trip(Base, IdMixin, TimestampMixin):
    __tablename__ = "trips"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    title: Mapped[str] = mapped_column(String(200), default="")
    origin_name: Mapped[str] = mapped_column(String(200), default="")
    origin_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_name: Mapped[str] = mapped_column(String(200))
    destination_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    num_travelers: Mapped[int] = mapped_column(Integer, default=1)

    total_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    # Trip style (e.g. relaxed/adventure/mixed) and free-form constraint text
    trip_style: Mapped[str] = mapped_column(String(50), default="")
    constraints: Mapped[str] = mapped_column(String(2000), default="")
    # Structured preferences: interests, food, accommodation, pace, etc.
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    # draft | planning | confirmed | completed
    status: Mapped[str] = mapped_column(String(20), default="draft")

    owner: Mapped[User] = relationship(back_populates="trips")  # noqa: F821
    days: Mapped[list[ItineraryDay]] = relationship(  # noqa: F821
        back_populates="trip", cascade="all, delete-orphan", order_by="ItineraryDay.day_number"
    )
    budget_items: Mapped[list[BudgetItem]] = relationship(  # noqa: F821
        back_populates="trip", cascade="all, delete-orphan"
    )
    preferences_per_person: Mapped[list[TripPreference]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )


class TripPreference(Base, IdMixin, TimestampMixin):
    """Per-traveler preferences for group travel (spec §20)."""

    __tablename__ = "trip_preferences"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    person_name: Mapped[str] = mapped_column(String(120), default="")
    # {"beach": 0.9, "food": 0.85, ...} normalized interest weights 0..1
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    trip: Mapped[Trip] = relationship(back_populates="preferences_per_person")
