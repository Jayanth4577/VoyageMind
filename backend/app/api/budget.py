"""Budget endpoints (spec §7/§24). All math lives in BudgetService."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models import BudgetItem
from app.schemas.budget_schema import BudgetItemCreate, BudgetItemOut, BudgetSummary
from app.services import budget_service
from app.services.trip_service import get_owned_trip

router = APIRouter(tags=["budget"])


@router.get("/trips/{trip_id}/budget", response_model=BudgetSummary)
def get_budget(trip_id: str, user: CurrentUser, db: DbSession) -> BudgetSummary:
    trip = get_owned_trip(db, trip_id, user)
    return budget_service.compute_summary(db, trip)


@router.post(
    "/trips/{trip_id}/budget",
    response_model=BudgetItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_budget_item(
    trip_id: str, body: BudgetItemCreate, user: CurrentUser, db: DbSession
) -> BudgetItem:
    trip = get_owned_trip(db, trip_id, user)
    if body.currency != trip.currency:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Currency {body.currency} does not match trip currency {trip.currency}",
        )
    item = BudgetItem(trip_id=trip.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/budget-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget_item(item_id: str, user: CurrentUser, db: DbSession) -> None:
    item = db.get(BudgetItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget item not found")
    get_owned_trip(db, item.trip_id, user)  # 404 unless the item belongs to this user's trip
    if item.source_ref.startswith("activity:"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This line mirrors an activity's estimated_cost; edit the activity instead",
        )
    db.delete(item)
    db.commit()
