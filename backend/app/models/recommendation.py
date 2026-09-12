"""AI recommendations with reason + source transparency (spec §17, §31)."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class Recommendation(Base, IdMixin, TimestampMixin):
    __tablename__ = "recommendations"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="ACTIVITY")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_suitability: Mapped[str] = mapped_column(String(30), default="")  # indoor/outdoor/any

    reason: Mapped[str] = mapped_column(String(1000), default="")
    data_source: Mapped[str] = mapped_column(String(80), default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # suggested | accepted | rejected
    status: Mapped[str] = mapped_column(String(20), default="suggested", index=True)

    trip: Mapped[Trip] = relationship()  # noqa: F821
