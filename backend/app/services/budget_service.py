"""BudgetService — the ONLY place trip money is computed (spec §7, §13).

The LLM may reason about the results but never performs this arithmetic.
"""
from sqlalchemy.orm import Session

from app.models import Activity, BudgetItem, Trip
from app.schemas.budget_schema import BudgetSummary

# Maps an activity category to its budget line category
ACTIVITY_BUDGET_CATEGORY = {
    "RESTAURANT": "food",
    "CAFE": "food",
    "FOOD": "food",
    "TRANSPORT": "local_transport",
    "FLIGHT": "transport",
    "TRAIN": "transport",
    "BUS": "transport",
}
DEFAULT_ACTIVITY_BUDGET_CATEGORY = "activities"

NEAR_BUDGET_RATIO = 0.9


def activity_budget_category(activity: Activity) -> str:
    return ACTIVITY_BUDGET_CATEGORY.get(activity.category.upper(), DEFAULT_ACTIVITY_BUDGET_CATEGORY)


def upsert_item_for_activity(db: Session, activity: Activity) -> None:
    """Mirror an activity's estimated_cost into its deterministic budget line."""
    ref = f"activity:{activity.id}"
    item = db.query(BudgetItem).filter(BudgetItem.source_ref == ref).one_or_none()
    if activity.estimated_cost and activity.estimated_cost > 0:
        if item is None:
            item = BudgetItem(
                trip_id=activity.trip_id,
                source_ref=ref,
                category=activity_budget_category(activity),
                label=activity.name,
                amount=activity.estimated_cost,
            )
            db.add(item)
        else:
            item.amount = activity.estimated_cost
            item.label = activity.name
            item.category = activity_budget_category(activity)
    elif item is not None:
        db.delete(item)


def remove_item_for_activity(db: Session, activity_id: str) -> None:
    ref = f"activity:{activity_id}"
    item = db.query(BudgetItem).filter(BudgetItem.source_ref == ref).one_or_none()
    if item is not None:
        db.delete(item)


def compute_summary(db: Session, trip: Trip) -> BudgetSummary:
    items = db.query(BudgetItem).filter(BudgetItem.trip_id == trip.id).all()

    by_category: dict[str, float] = {}
    for item in items:
        by_category[item.category] = by_category.get(item.category, 0.0) + item.amount
    spent = round(sum(by_category.values()), 2)

    budget = trip.total_budget
    if budget is None:
        state, remaining = "unknown", None
    elif spent > budget:
        state, remaining = "over", round(budget - spent, 2)  # negative
    elif budget > 0 and spent >= NEAR_BUDGET_RATIO * budget:
        state, remaining = "near", round(budget - spent, 2)
    else:
        state, remaining = "under", round(budget - spent, 2)

    return BudgetSummary(
        trip_id=trip.id,
        currency=trip.currency,
        total_budget=budget,
        spent=spent,
        remaining=remaining,
        by_category={k: round(v, 2) for k, v in sorted(by_category.items())},
        state=state,
    )
