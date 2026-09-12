"""Budget line items — deterministic totals are computed in BudgetService, never by the LLM."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class BudgetItem(Base, IdMixin, TimestampMixin):
    __tablename__ = "budget_items"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    # transport | accommodation | food | activities | local_transport | buffer
    category: Mapped[str] = mapped_column(String(30), index=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    # manual | activity:<id> | transport:<id> | ...
    source_ref: Mapped[str] = mapped_column(String(80), default="manual")

    trip: Mapped[Trip] = relationship(back_populates="budget_items")  # noqa: F821
