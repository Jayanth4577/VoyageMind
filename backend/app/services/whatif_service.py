"""WhatIfService — impact simulation engine (spec §6.8).

Simulates scenarios (flight delay, rain, budget change, etc.) against
the current itinerary using real tools and services. Returns an impact
chain showing what would change.
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Trip
from app.services.budget_service import compute_summary

logger = get_logger(__name__)

# Scenario handlers registry
_SCENARIOS = {}


def scenario(name: str):
    """Decorator to register a scenario handler."""
    def wrapper(fn):
        _SCENARIOS[name] = fn
        return fn
    return wrapper


async def simulate(
    db: Session, trip: Trip, scenario_name: str, params: dict
) -> dict:
    """Run a what-if simulation."""
    handler = _SCENARIOS.get(scenario_name)
    if handler is None:
        return {
            "scenario": scenario_name,
            "parameters": params,
            "impact_chain": [f"Unknown scenario: {scenario_name}"],
            "reasoning": "Scenario not supported",
        }
    try:
        return await handler(db, trip, params)
    except Exception as exc:
        logger.error("Simulation error for %s: %s", scenario_name, exc)
        return {
            "scenario": scenario_name,
            "parameters": params,
            "impact_chain": [f"Simulation error: {exc}"],
            "reasoning": str(exc),
        }


@scenario("rain")
async def _sim_rain(db: Session, trip: Trip, params: dict) -> dict:
    """Simulate rain on specific days."""
    target_days = params.get("days", [1])
    chain = []
    affected_activities = []
    suggestions = []

    for day in sorted(trip.days, key=lambda d: d.day_number):
        if day.day_number not in target_days:
            continue
        outdoor = [
            a for a in day.activities
            if a.weather_sensitive and not a.indoor
        ]
        if outdoor:
            names = [a.name for a in outdoor]
            affected_activities.extend(names)
            chain.append(
                f"Day {day.day_number}: {len(outdoor)} outdoor "
                f"activities affected by rain"
            )
            for a in outdoor:
                suggestions.append({
                    "change_type": "swap_activity",
                    "target_day": day.day_number,
                    "target_activity_id": a.id,
                    "proposed_data": {
                        "name": f"Indoor alternative for {a.name}",
                        "indoor": True,
                        "weather_sensitive": False,
                    },
                    "problem": f"Rain on day {day.day_number}",
                    "reason": f"{a.name} is weather-sensitive outdoor",
                })

    return {
        "scenario": "rain",
        "parameters": params,
        "impact_chain": chain or ["No outdoor activities affected"],
        "affected_days": target_days,
        "affected_activities": affected_activities,
        "budget_delta": 0.0,
        "time_delta_minutes": 0,
        "contingency_triggered": ["RAIN"] if affected_activities else [],
        "suggestions": suggestions,
        "reasoning": (
            f"{len(affected_activities)} weather-sensitive outdoor "
            "activities would need alternatives"
            if affected_activities
            else "No impact — all activities are indoor or not weather-sensitive"
        ),
    }


@scenario("flight_delay")
async def _sim_flight_delay(db: Session, trip: Trip, params: dict) -> dict:
    """Simulate a flight delay."""
    delay_hours = params.get("delay_hours", 3)
    delay_minutes = delay_hours * 60
    chain = [
        f"Flight delayed by {delay_hours} hours",
        f"Arrival pushed back {delay_minutes} minutes",
    ]
    affected = []

    # Day 1 activities are most affected
    day1 = next(
        (d for d in trip.days if d.day_number == 1), None
    )
    if day1:
        for a in day1.activities:
            affected.append(a.name)
        if affected:
            chain.append(
                f"Day 1: {len(affected)} activities may need rescheduling"
            )

    return {
        "scenario": "flight_delay",
        "parameters": params,
        "impact_chain": chain,
        "affected_days": [1],
        "affected_activities": affected,
        "budget_delta": 0.0,
        "time_delta_minutes": delay_minutes,
        "contingency_triggered": ["FLIGHT_DELAY"],
        "suggestions": [{
            "change_type": "reschedule",
            "target_day": 1,
            "proposed_data": {"delay_minutes": delay_minutes},
            "problem": f"Flight delayed by {delay_hours}h",
            "reason": "Reschedule Day 1 activities",
        }] if affected else [],
        "reasoning": (
            f"Flight delay of {delay_hours}h would affect "
            f"{len(affected)} Day 1 activities"
        ),
    }


@scenario("budget_change")
async def _sim_budget_change(db: Session, trip: Trip, params: dict) -> dict:
    """Simulate a budget increase or decrease."""
    new_budget = params.get("new_budget")
    if new_budget is None:
        return {
            "scenario": "budget_change",
            "parameters": params,
            "impact_chain": ["No new_budget specified"],
            "reasoning": "Provide new_budget parameter",
        }

    current = trip.total_budget or 0
    delta = new_budget - current
    summary = compute_summary(db, trip)

    would_be_remaining = new_budget - summary.spent
    chain = [
        f"Budget changed: {current} → {new_budget} ({'+' if delta > 0 else ''}{delta})",
        f"Current spending: {summary.spent}",
        f"Would-be remaining: {would_be_remaining}",
    ]

    if would_be_remaining < 0:
        chain.append("⚠ Would be OVER BUDGET")

    return {
        "scenario": "budget_change",
        "parameters": params,
        "impact_chain": chain,
        "affected_days": [],
        "affected_activities": [],
        "budget_delta": delta,
        "time_delta_minutes": 0,
        "contingency_triggered": (
            ["BUDGET_OVERRUN"] if would_be_remaining < 0 else []
        ),
        "suggestions": [],
        "reasoning": (
            f"Budget {'increase' if delta > 0 else 'decrease'} "
            f"of {abs(delta)} {trip.currency or 'INR'}"
        ),
    }


@scenario("fewer_travelers")
async def _sim_fewer_travelers(db: Session, trip: Trip, params: dict) -> dict:
    """Simulate fewer travelers."""
    new_count = params.get("new_count", max(1, (trip.num_travelers or 2) - 1))
    old_count = trip.num_travelers or 2
    delta_count = old_count - new_count

    summary = compute_summary(db, trip)
    # Rough estimate: per-person costs might reduce proportionally
    estimated_saving = round(
        summary.spent * (delta_count / old_count) * 0.3, 2
    ) if old_count > 0 else 0

    chain = [
        f"Travelers reduced: {old_count} → {new_count}",
        f"Estimated per-person cost savings: ~{estimated_saving}",
    ]

    return {
        "scenario": "fewer_travelers",
        "parameters": params,
        "impact_chain": chain,
        "affected_days": [],
        "affected_activities": [],
        "budget_delta": -estimated_saving,
        "time_delta_minutes": 0,
        "contingency_triggered": [],
        "suggestions": [],
        "reasoning": (
            f"Reducing from {old_count} to {new_count} travelers "
            f"could save approximately {estimated_saving}"
        ),
    }


@scenario("hotel_unavailable")
async def _sim_hotel_unavailable(db: Session, trip: Trip, params: dict) -> dict:
    """Simulate hotel becoming unavailable."""
    chain = [
        "Current accommodation unavailable",
        "Need to find alternative accommodation",
        "May affect budget and proximity to activities",
    ]

    return {
        "scenario": "hotel_unavailable",
        "parameters": params,
        "impact_chain": chain,
        "affected_days": list(range(1, len(trip.days) + 1)),
        "affected_activities": [],
        "budget_delta": 0.0,
        "time_delta_minutes": 0,
        "contingency_triggered": ["HOTEL_ISSUE"],
        "suggestions": [],
        "reasoning": (
            "Hotel unavailability affects all days. "
            "Use the search_stays tool to find alternatives."
        ),
    }


@scenario("extra_day")
async def _sim_extra_day(db: Session, trip: Trip, params: dict) -> dict:
    """Simulate adding an extra day."""
    current_days = len(trip.days)
    new_total = current_days + 1

    summary = compute_summary(db, trip)
    per_day_cost = round(
        summary.spent / current_days, 2
    ) if current_days > 0 else 0

    chain = [
        f"Trip extended: {current_days} → {new_total} days",
        f"Estimated additional cost: ~{per_day_cost} per day",
        "Additional accommodation night needed",
    ]

    remaining = (summary.total_budget or 0) - summary.spent
    if per_day_cost > remaining:
        chain.append("⚠ May exceed budget")

    return {
        "scenario": "extra_day",
        "parameters": params,
        "impact_chain": chain,
        "affected_days": [new_total],
        "affected_activities": [],
        "budget_delta": per_day_cost,
        "time_delta_minutes": 0,
        "contingency_triggered": (
            ["BUDGET_OVERRUN"] if per_day_cost > remaining else []
        ),
        "suggestions": [],
        "reasoning": (
            f"Adding day {new_total} would cost approximately "
            f"{per_day_cost} {trip.currency or 'INR'}"
        ),
    }
