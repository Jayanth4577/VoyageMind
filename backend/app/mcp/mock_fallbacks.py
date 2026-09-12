"""Labeled demo/mock fallbacks mirroring the gateway's tool output shapes.

Used when the MCP gateway or its providers are unreachable. Every payload is
unmistakably marked (spec §25: never mislead the user with fake data).
"""
from datetime import UTC, datetime

from app.utils.geo_utils import haversine_km


def _meta() -> dict:
    return {
        "source": "mock",
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "is_mock": True,
    }


def mock_weather(latitude: float, longitude: float, days: int = 5) -> dict:
    return {
        **_meta(),
        "note": "DEMO DATA — synthetic weather (gateway/provider unavailable)",
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
            for i in range(max(1, min(days, 16)))
        ],
        "air_quality": None,
        "alerts": [],
    }


def mock_geocode(name: str) -> dict:
    return {
        **_meta(),
        "note": "DEMO DATA — synthetic coordinates (gateway/provider unavailable)",
        "query": name,
        "results": [
            {"name": name.title(), "latitude": 15.2993, "longitude": 74.124, "country": "Demo"}
        ],
    }


def mock_route(points: list[dict]) -> dict:
    legs = []
    for i, (a, b) in enumerate(zip(points, points[1:], strict=False)):
        km = haversine_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
        legs.append(
            {
                "from": f"point{i}",
                "to": f"point{i + 1}",
                "distance_km": round(km, 1),
                "duration_minutes": round(km / 40 * 60),
            }
        )
    total_km = round(sum(leg["distance_km"] for leg in legs), 1)
    return {
        **_meta(),
        "note": (
            "DEMO DATA — straight-line distance at an assumed 40 km/h "
            "(gateway unavailable)"
        ),
        "distance_km": total_km,
        "duration_minutes": round(sum(leg["duration_minutes"] for leg in legs)),
        "legs": legs,
    }


def mock_nearby(latitude: float, longitude: float, category: str, limit: int = 8) -> dict:
    return {
        **_meta(),
        "note": "DEMO DATA — synthetic nearby places (gateway/provider unavailable)",
        "query": {"latitude": latitude, "longitude": longitude, "category": category},
        "results": [
            {
                "name": f"Demo {category} {i + 1}",
                "category": category,
                "latitude": latitude + 0.001 * i,
                "longitude": longitude + 0.001 * i,
                "distance_km": round(0.15 * (i + 1), 2),
            }
            for i in range(limit)
        ],
    }


def mock_transport(origin: str, destination: str, date: str) -> dict:
    return {
        **_meta(),
        "note": "DEMO DATA — synthetic flights (gateway/provider unavailable)",
        "query": {"origin": origin, "destination": destination, "date": date},
        "offers": [
            {
                "id": f"demo-offer-{i + 1}",
                "airline": airline,
                "departure_at": f"{date}T{dep}:00",
                "arrival_at": f"{date}T{arr}:00",
                "duration_minutes": 90,
                "price": price,
                "currency": "INR",
            }
            for i, (airline, dep, arr, price) in enumerate(
                [("DemoAir", "07:30", "09:00", 3500), ("DemoJet", "14:00", "15:30", 4200)]
            )
        ],
    }


def mock_stays(location: str, check_in: str, check_out: str, guests: int = 2) -> dict:
    return {
        **_meta(),
        "note": "DEMO DATA — synthetic stays (gateway/provider unavailable)",
        "query": {
            "location": location,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
        },
        "stays": [
            {
                "id": f"demo-stay-{i + 1}",
                "name": name,
                "location_name": location,
                "price_per_night": nightly,
                "rating": rating,
                "guests_per_room": 2,
            }
            for i, (name, nightly, rating) in enumerate(
                [
                    ("Demo Beach Guesthouse", 2200, 7.8),
                    ("Demo City Hotel", 3100, 8.2),
                ]
            )
        ],
    }
