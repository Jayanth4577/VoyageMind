"""Weather tools (Open-Meteo). Live forecast + air quality, labeled demo fallback."""
import os

from travel_mcp.tools.common import get_client, is_demo_mode, meta

FORECAST_URL = os.environ.get("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1") + "/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# WMO weather interpretation codes that mean "significant rain"
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


def _mock_weather(latitude: float, longitude: float, days: int) -> dict:
    return {
        **meta("mock", True),
        "note": "DEMO DATA — synthetic weather, never use for real decisions",
        "latitude": latitude,
        "longitude": longitude,
        "current": {"temperature_c": 28.0, "precipitation_mm": 0.0, "weather_code": 0},
        "daily": [
            {
                "date": f"demo-day-{i + 1}",
                "temp_max_c": 30.0,
                "temp_min_c": 24.0,
                "precipitation_mm": 0.0 if i % 3 else 4.0,
                "rain_probability": 5 if i % 3 else 70,
                "weather_code": 0 if i % 3 else 61,
                "significant_rain": i % 3 == 0,
            }
            for i in range(min(days, 16))
        ],
        "air_quality": None,
        "alerts": [],
        "provider_note": "Open-Meteo provides no severe-weather alert feed; check local advisories",
    }


async def get_weather(latitude: float, longitude: float, days: int = 5) -> dict:
    """Multi-day forecast: temperature, precipitation, rain probability, air quality."""
    if is_demo_mode():
        return _mock_weather(latitude, longitude, days)

    days = max(1, min(days, 16))
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "precipitation_probability_max,weather_code",
        "current": "temperature_2m,precipitation,weather_code",
        "timezone": "auto",
        "forecast_days": days,
    }
    try:
        resp = await get_client().get(FORECAST_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — tools degrade, never raise
        return {"status": "error", "error": f"weather provider failed: {exc}"}

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    forecast = [
        {
            "date": dates[i],
            "temp_max_c": (daily.get("temperature_2m_max") or [None] * len(dates))[i],
            "temp_min_c": (daily.get("temperature_2m_min") or [None] * len(dates))[i],
            "precipitation_mm": (daily.get("precipitation_sum") or [None] * len(dates))[i],
            "rain_probability": (daily.get("precipitation_probability_max") or [None] * len(dates))[i],
            "weather_code": (daily.get("weather_code") or [None] * len(dates))[i],
            "significant_rain": ((daily.get("weather_code") or [])[i] in RAIN_CODES)
            or ((daily.get("precipitation_sum") or [0] * len(dates))[i] or 0) >= 5,
        }
        for i in range(len(dates))
    ]

    current_raw = data.get("current", {})
    current = {
        "temperature_c": current_raw.get("temperature_2m"),
        "precipitation_mm": current_raw.get("precipitation"),
        "weather_code": current_raw.get("weather_code"),
    }

    # Air quality is best-effort; its failure must not fail the forecast.
    air_quality = None
    try:
        aq = await get_client().get(
            AIR_QUALITY_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "pm10,pm2_5,us_aqi",
                "timezone": "auto",
            },
        )
        if aq.status_code == 200:
            air_quality = aq.json().get("current")
    except Exception:  # noqa: BLE001, S110
        pass

    return {
        **meta("open-meteo", False),
        "latitude": latitude,
        "longitude": longitude,
        "current": current,
        "daily": forecast,
        "air_quality": air_quality,
        "alerts": [],
        "provider_note": "Open-Meteo provides no severe-weather alert feed; check local advisories",
    }
