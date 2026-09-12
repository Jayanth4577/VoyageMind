"""OptimizationService — itinerary & budget optimization (spec §7/§8/§4).

All computations are deterministic backend logic. Budget savings candidates are
derived from real budget lines via same-category medians; nothing is invented.
"""

from statistics import median

from sqlalchemy.orm import Session

from app.models import BudgetItem, Trip
from app.services import conflict_service, route_service
from app.services.budget_service import compute_summary


async def optimize_itinerary(db: Session, trip: Trip) -> dict:
    """Route optimization per day + schedule feasibility, in one report."""
    route_report = await route_service.itinerary_route_report(db, trip)
    conflicts = conflict_service.validate_itinerary(db, trip)
    return {
        "trip_id": trip.id,
        "status": "ok",
        "route": route_report,
        "schedule_conflicts": conflicts,
        "total_saved_minutes": route_report.get("total_saved_minutes", 0),
    }


async def optimize_day(db: Session, trip: Trip, day) -> dict:
    report = await route_service.day_route_report(db, trip, day)
    return {
        "trip_id": trip.id,
        "days": [report],
        "total_saved_minutes": report.get("saved_minutes", 0),
    }


def budget_savings_plan(db: Session, trip: Trip) -> dict:
    """Deterministic savings candidates when the trip is over budget."""
    summary = compute_summary(db, trip)
    if summary.total_budget is None:
        return {
            "trip_id": trip.id,
            "status": "no_budget",
            "message": "Set a total budget to get savings suggestions",
        }

    over = round(summary.spent - summary.total_budget, 2)
    if over <= 0:
        return {
            "trip_id": trip.id,
            "status": "on_track",
            "state": summary.state,
            "spent": summary.spent,
            "total_budget": summary.total_budget,
            "currency": summary.currency,
        }

    items = db.query(BudgetItem).filter(BudgetItem.trip_id == trip.id).all()
    by_category: dict[str, list[BudgetItem]] = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)

    candidates = []
    for category, cat_items in by_category.items():
        if len(cat_items) < 2:
            continue  # no comparison basis — handled via review list below
        amounts = [i.amount for i in cat_items]
        for item in cat_items:
            others = list(amounts)
            others.remove(item.amount)
            target = median(others)
            saving = round(item.amount - target, 2)
            if saving > 0:
                candidates.append(
                    {
                        "budget_item_id": item.id,
                        "label": item.label,
                        "category": category,
                        "current_amount": item.amount,
                        "target_amount": round(target, 2),
                        "potential_saving": saving,
                        "rationale": (
                            f"Median {category} line for this trip is "
                            f"{round(target, 2)} {summary.currency}"
                        ),
                    }
                )
    candidates.sort(key=lambda c: c["potential_saving"], reverse=True)

    plan, covered = [], 0.0
    for candidate in candidates:
        if covered >= over:
            break
        plan.append(candidate)
        covered += candidate["potential_saving"]

    review = [
        {"budget_item_id": i.id, "label": i.label, "category": i.category, "amount": i.amount}
        for i in sorted(items, key=lambda x: x.amount, reverse=True)[:3]
    ]

    return {
        "trip_id": trip.id,
        "status": "over_budget",
        "over_budget_amount": over,
        "currency": summary.currency,
        "candidates": plan,
        "potential_total_saving": round(min(covered, over), 2),
        "covers_shortfall": covered >= over,
        "review_largest_lines": review,
        "note": (
            "Deterministic suggestions from this trip's own budget lines; "
            "the Budget Agent (Phase 5) can search real cheaper alternatives"
        ),
    }
