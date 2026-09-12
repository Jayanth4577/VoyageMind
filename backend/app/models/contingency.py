"""Contingency plans as structured decision-tree nodes (spec §6) — not prose."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class Contingency(Base, IdMixin, TimestampMixin):
    __tablename__ = "contingencies"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)

    # A (original) | B (weather) | C (transport) | D (accommodation) | E (other)
    plan_level: Mapped[str] = mapped_column(String(2), default="A")
    # RAIN | FLIGHT_DELAY | HOTEL_ISSUE | BUDGET_OVERRUN | OTHER
    trigger: Mapped[str] = mapped_column(String(40), index=True)
    # Machine-checkable, e.g. "rain_probability > 0.6"
    condition: Mapped[str] = mapped_column(String(300), default="")
    affected_activity_ids: Mapped[list] = mapped_column(JSON, default=list)
    fallback_plan: Mapped[list] = mapped_column(JSON, default=list)  # ordered fallback steps

    budget_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_impact_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(String(1000), default="")
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)

    # proposed | accepted | dismissed | activated
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)

    trip: Mapped[Trip] = relationship()  # noqa: F821
