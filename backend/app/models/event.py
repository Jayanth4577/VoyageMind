"""Audit trail (spec §28 observability: approvals, rejections, agent runs) + copilot chat."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class TripEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "trip_events"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    # user | ai | system
    actor: Mapped[str] = mapped_column(String(10), default="user")
    # suggestion_accepted | suggestion_rejected | agent_run | tool_call | ...
    kind: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    trip: Mapped[Trip] = relationship()  # noqa: F821


class CopilotMessage(Base, IdMixin, TimestampMixin):
    __tablename__ = "copilot_messages"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    # user | assistant | system
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text, default="")
    # Structured side-car: suggested_change, tool trace, sources used, ...
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    trip: Mapped[Trip] = relationship()  # noqa: F821
