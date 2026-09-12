"""WeatherService — deterministic weather-risk assessment (spec §5).

Thresholds turn real forecast data into per-day risks and affected activities.
Suggestions are rule-based text, clearly separate from the forecast itself;
the Weather/Risk Agent (Phase 5) reasons on top of this structured report.
"""

from sqlalchemy.orm import Session

from app.mcp.travel_mcp import travel_mcp
from app.models import ItineraryDay, Trip
from app.services.trip_service import resolve_trip_coordinates

RAIN_PROBABILITY_THRESHOLD = 60  # percent
RAIN_MM_THRESHOLD = 5.0  # mm/day
HEAT_THRESHOLD_C = 38.0  # daily max

SUGGESTIONS = {
    "rain": (
        "Significant rain forecast: prefer indoor alternatives (museum, cafe, "
        "shopping) or move outdoor activities to a drier day"
    ),
    "heat": (
        "Extreme heat forecast: schedule outdoor sightseeing for early morning "
        "or evening; keep midday indoors (food, rest)"
    ),
    "severe": (
        "Severe weather alert: reconsider outdoor plans for this day and "
        "monitor official advisories"
    ),
}


def _assess_day(day: ItineraryDay, forecast_day: dict | None, has_alerts: bool) -> dict:
    risk = "none"
    reasons: list[str] = []

    if forecast_day:
        rain_prob = forecast_day.get("rain_probability")
        precip = forecast_day.get("precipitation_mm")
        temp_max = forecast_day.get("temp_max_c")
        significant_rain = forecast_day.get("significant_rain")

        if temp_max is not None and temp_max >= HEAT_THRESHOLD_C:
            risk = "heat"
            reasons.append(f"daily max {temp_max}°C ≥ {HEAT_THRESHOLD_C}°C")
        if (
            significant_rain
            or (rain_prob is not None and rain_prob >= RAIN_PROBABILITY_THRESHOLD)
            or (precip is not None and precip >= RAIN_MM_THRESHOLD)
        ):
            risk = "rain"
            parts = []
            if rain_prob is not None:
                parts.append(f"rain probability {rain_prob}%")
            if precip is not None:
                parts.append(f"precipitation {precip} mm")
            reasons.append(" / ".join(parts) or "significant rain flag")
    if has_alerts and risk != "severe":
        risk = "severe"
        reasons.append("provider severe-weather alert present")

    affected_ids = []
    if risk != "none":
        affected_ids = [a.id for a in day.activities if a.weather_sensitive and not a.indoor]

    return {
        "day_id": day.id,
        "day_number": day.day_number,
        "date": str(day.date) if day.date else None,
        "risk": risk,
        "reasons": reasons,
        "forecast": forecast_day,
        "affected_activity_ids": affected_ids,
        "suggestion": SUGGESTIONS[risk] if risk != "none" else "",
    }


async def check_weather_conflicts(db: Session, trip: Trip) -> dict:
    coordinates = await resolve_trip_coordinates(db, trip)
    if coordinates is None:
        return {
            "trip_id": trip.id,
            "status": "unresolved_location",
            "message": "Destination could not be geocoded; no weather assessment possible",
            "days": [],
        }
    latitude, longitude = coordinates

    n_days = max(1, len(trip.days))
    forecast = await travel_mcp.weather.get_weather(latitude, longitude, days=n_days)
    daily = forecast.get("daily") or []
    has_alerts = bool(forecast.get("alerts"))

    # Match forecast days to itinerary days by date where possible; fall back to
    # positional matching (demo data carries synthetic dates like "demo-day-1").
    by_date = {}
    for entry in daily:
        date_key = entry.get("date")
        if date_key and len(str(date_key)) == 10:
            by_date[str(date_key)] = entry

    day_reports = []
    for day in sorted(trip.days, key=lambda d: d.day_number):
        entry = by_date.get(str(day.date)) if day.date else None
        if entry is None and 0 <= day.day_number - 1 < len(daily):
            entry = daily[day.day_number - 1]
        day_reports.append(_assess_day(day, entry, has_alerts))

    risky = [d for d in day_reports if d["risk"] != "none"]
    return {
        "trip_id": trip.id,
        "status": "ok",
        "source": forecast.get("source"),
        "is_mock": forecast.get("is_mock"),
        "days": day_reports,
        "days_at_risk": len(risky),
        "affected_activity_count": sum(len(d["affected_activity_ids"]) for d in risky),
    }
