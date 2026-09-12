"""Transport options and accommodations — raw search results kept for comparison (spec §4)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class TransportOption(Base, IdMixin, TimestampMixin):
    __tablename__ = "transport_options"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    # flight | train | bus | car | other
    kind: Mapped[str] = mapped_column(String(20), default="flight")
    provider: Mapped[str] = mapped_column(String(80), default="")

    origin_name: Mapped[str] = mapped_column(String(200), default="")
    destination_name: Mapped[str] = mapped_column(String(200), default="")
    departure_at: Mapped[str] = mapped_column(String(40), default="")
    arrival_at: Mapped[str] = mapped_column(String(40), default="")
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Float, nullable=True)

    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    source: Mapped[str] = mapped_column(String(40), default="")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    trip: Mapped[Trip] = relationship()  # noqa: F821


class Accommodation(Base, IdMixin, TimestampMixin):
    __tablename__ = "accommodations"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(80), default="")

    location_name: Mapped[str] = mapped_column(String(200), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    check_in: Mapped[date | None] = mapped_column(Date, nullable=True)
    check_out: Mapped[date | None] = mapped_column(Date, nullable=True)
    price_per_night: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(40), default="")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    trip: Mapped[Trip] = relationship()  # noqa: F821
