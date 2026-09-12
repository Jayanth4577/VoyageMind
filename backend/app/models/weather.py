"""Cached weather snapshots with source transparency (who/when/mock)."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class WeatherSnapshot(Base, IdMixin, TimestampMixin):
    __tablename__ = "weather_snapshots"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    source: Mapped[str] = mapped_column(String(60), default="")  # e.g. open-meteo
    fetched_at: Mapped[str] = mapped_column(String(40), default="")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    # Provider payload: daily forecast, rain probability, alerts, AQI, ...
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    trip: Mapped[Trip] = relationship()  # noqa: F821
