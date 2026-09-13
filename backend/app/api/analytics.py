"""Analytics endpoints — deterministic per-trip and aggregate spending (spec §7).

All arithmetic stays in backend services; the UI only renders these numbers.
"""
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Trip
from app.services.budget_service import compute_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def analytics_summary(user: CurrentUser, db: DbSession) -> dict:
    """Per-trip spending breakdown + aggregate totals across all owned trips."""
    from datetime import date

    trips = db.scalars(select(Trip).where(Trip.owner_id == user.id)).all()

    per_trip = []
    totals_by_currency: dict[str, dict] = {}
    for trip in sorted(trips, key=lambda t: t.start_date):
        summary = compute_summary(db, trip)
        activity_count = sum(len(d.activities) for d in trip.days)
        per_trip.append(
            {
                "trip_id": trip.id,
                "title": trip.title or trip.destination_name,
                "destination_name": trip.destination_name,
                "origin_name": trip.origin_name,
                "start_date": str(trip.start_date),
                "end_date": str(trip.end_date),
                "status": trip.status,
                "num_travelers": trip.num_travelers,
                "activity_count": activity_count,
                "total_budget": summary.total_budget,
                "spent": summary.spent,
                "remaining": summary.remaining,
                "state": summary.state,
                "by_category": summary.by_category,
                "currency": summary.currency,
            }
        )
        bucket = totals_by_currency.setdefault(
            summary.currency,
            {"total_budget": 0.0, "total_spent": 0.0, "by_category": {}, "trips": 0},
        )
        bucket["trips"] += 1
        bucket["total_budget"] += summary.total_budget or 0.0
        bucket["total_spent"] += summary.spent
        for cat, amt in summary.by_category.items():
            bucket["by_category"][cat] = bucket["by_category"].get(cat, 0.0) + amt

    today = date.today()
    upcoming = next(
        (
            t
            for t in per_trip
            if t["start_date"] >= today.isoformat()
        ),
        None,
    )

    return {
        "trip_count": len(per_trip),
        "trips": per_trip,
        "totals_by_currency": totals_by_currency,
        "upcoming": upcoming,
    }
