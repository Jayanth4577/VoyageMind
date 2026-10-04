"""Maps tools: geocoding (Open-Meteo/Nominatim), routing (OSRM), places (Overpass)."""
import itertools
import os

from travel_mcp.tools.common import get_client, is_demo_mode, meta
from travel_mcp.tools.weather import _mock_weather  # noqa: F401 (re-exported for tests)

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OSRM_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
# Primary endpoint + public mirrors — overpass-api.de rate-limits some
# datacenter IPs (e.g. Render), so every query walks the list on failure.
OVERPASS_URLS = [
    os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter"),
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


async def overpass_query(query: str) -> dict:
    """Run an Overpass query, falling back through the public mirrors."""
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            resp = await get_client().post(url, data={"data": query})
            if resp.status_code in (429, 502, 503, 504):
                last_error = Exception(f"{url} returned {resp.status_code}")
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise last_error or Exception("all Overpass endpoints failed")

# Overpass filter per supported nearby-place category
OVERPASS_FILTERS = {
    "restaurant": 'node["amenity"="restaurant"]',
    "cafe": 'node["amenity"="cafe"]',
    "museum": 'node["tourism"="museum"]',
    "attraction": 'node["tourism"="attraction"]',
    "hotel": 'node["tourism"="hotel"]',
    "supermarket": 'node["shop"="supermarket"]',
    "pharmacy": 'node["amenity"="pharmacy"]',
    "beach": 'node["natural"="beach"]',
    "temple": 'node["amenity"="place_of_worship"]',
    "market": 'node["amenity"="marketplace"]',
    "viewpoint": 'node["tourism"="viewpoint"]',
    "garden": 'node["leisure"="garden"]',
    "waterfall": 'node["natural"="waterfall"]',
    "monument": 'node["historic"="monument"]',
    "artwork": 'node["tourism"="artwork"]',
    "zoo": 'node["tourism"="zoo"]',
}


def _haversine_km(lat1, lng1, lat2, lng2):
    from math import asin, cos, radians, sin, sqrt

    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


async def geocode_place(name: str, count: int = 1) -> dict:
    """Resolve a place name to coordinates (Open-Meteo geocoding, no API key)."""
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — synthetic geocoding",
            "results": [
                {
                    "name": name.title(),
                    "latitude": 15.2993,
                    "longitude": 74.124,
                    "country": "Demo",
                }
            ],
        }
    try:
        resp = await get_client().get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": count, "language": "en", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"geocoding failed: {exc}"}

    results = [
        {
            "name": r.get("name", ""),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "country": r.get("country"),
            "admin1": r.get("admin1"),
            # lets callers size searches to the place (metro vs rural)
            "population": r.get("population"),
        }
        for r in data.get("results", [])[:count]
    ]
    return {**meta("open-meteo-geocoding", False), "query": name, "results": results}


async def calculate_route(points: list[dict]) -> dict:
    """Real road distance/duration for an ordered list of {latitude, longitude} (OSRM)."""
    if len(points) < 2:
        return {"status": "error", "error": "route needs at least 2 points"}
    if is_demo_mode():
        total_km = sum(
            _haversine_km(
                a["latitude"], a["longitude"], b["latitude"], b["longitude"]
            )
            for a, b in itertools.pairwise(points)
        )
        return {
            **meta("mock", True),
            "note": "DEMO DATA — straight-line distance at an assumed 40 km/h",
            "distance_km": round(total_km, 1),
            "duration_minutes": round(total_km / 40 * 60),
            "legs": [
                {
                    "from": f"point{i}",
                    "to": f"point{i + 1}",
                    "distance_km": round(
                        _haversine_km(
                            a["latitude"], a["longitude"], b["latitude"], b["longitude"]
                        ),
                        1,
                    ),
                    "duration_minutes": round(
                        _haversine_km(
                            a["latitude"], a["longitude"], b["latitude"], b["longitude"]
                        )
                        / 40
                        * 60
                    ),
                }
                for i, (a, b) in enumerate(itertools.pairwise(points))
            ],
        }

    coords = ";".join(f"{p['longitude']},{p['latitude']}" for p in points)
    try:
        resp = await get_client().get(f"{OSRM_URL}/route/v1/driving/{coords}")
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"routing failed: {exc}"}

    routes = data.get("routes") or []
    if not routes:
        return {"status": "error", "error": f"no route found: {data.get('code')}"}
    route = routes[0]
    legs = [
        {
            "from": f"point{i}",
            "to": f"point{i + 1}",
            "distance_km": round(leg["distance"] / 1000, 1),
            "duration_minutes": round(leg["duration"] / 60),
        }
        for i, leg in enumerate(route.get("legs", []))
    ]
    return {
        **meta("osrm", False),
        "distance_km": round(route["distance"] / 1000, 1),
        "duration_minutes": round(route["duration"] / 60),
        "legs": legs,
    }


async def optimize_route(points: list[dict]) -> dict:
    """Optimal visiting order for the given points (OSRM trip service, keeps first fixed).

    Returns `order`: indices into the input list in recommended visiting order.
    """
    if len(points) < 2:
        return {"status": "error", "error": "route optimization needs at least 2 points"}
    if is_demo_mode():
        # Deterministic demo: nearest-neighbor from the first point
        remaining = list(range(1, len(points)))
        order, cur = [0], 0
        while remaining:
            nxt = min(
                remaining,
                key=lambda j: _haversine_km(
                    points[cur]["latitude"], points[cur]["longitude"],
                    points[j]["latitude"], points[j]["longitude"],
                ),
            )
            order.append(nxt)
            remaining.remove(nxt)
            cur = nxt
        total_km = sum(
            _haversine_km(
                points[a]["latitude"], points[a]["longitude"],
                points[b]["latitude"], points[b]["longitude"],
            )
            for a, b in itertools.pairwise(order)
        )
        return {
            **meta("mock", True),
            "note": "DEMO DATA — nearest-neighbor ordering, straight-line at 40 km/h",
            "order": order,
            "distance_km": round(total_km, 1),
            "duration_minutes": round(total_km / 40 * 60),
        }

    coords = ";".join(f"{p['longitude']},{p['latitude']}" for p in points)
    try:
        resp = await get_client().get(
            f"{OSRM_URL}/trip/v1/driving/{coords}", params={"source": "first", "roundtrip": "false"}
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"route optimization failed: {exc}"}

    trips = data.get("trips") or []
    if not trips:
        return {"status": "error", "error": f"no trip found: {data.get('code')}"}
    trip = trips[0]
    # OSRM returns waypoints in optimized order; waypoint_index maps to input order
    order = [w["waypoint_index"] for w in trip.get("waypoints", [])]
    legs = [
        {
            "from": f"point{a}",
            "to": f"point{b}",
            "duration_minutes": round(leg["duration"] / 60),
        }
        for (a, b), leg in zip(
            itertools.pairwise(order), trip.get("legs", []), strict=False
        )
    ]
    return {
        **meta("osrm", False),
        "order": order,
        "distance_km": round(trip["distance"] / 1000, 1),
        "duration_minutes": round(trip["duration"] / 60),
        "legs": legs,
    }


async def search_places(query: str, count: int = 5) -> dict:
    """Free-text place search (Nominatim / OpenStreetMap)."""
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — synthetic places",
            "results": [
                {
                    "name": f"{query.title()} (demo)",
                    "category": "attraction",
                    "latitude": 15.2993,
                    "longitude": 74.124,
                    "osm_id": 100000 + i,
                }
                for i in range(count)
            ],
        }
    try:
        resp = await get_client().get(
            f"{NOMINATIM_URL}/search",
            params={"q": query, "format": "jsonv2", "limit": count},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"place search failed: {exc}"}

    results = [
        {
            "name": r.get("name") or r.get("display_name", ""),
            "display_name": r.get("display_name"),
            "category": r.get("category") or r.get("class"),
            "type": r.get("type"),
            "latitude": float(r["lat"]) if r.get("lat") else None,
            "longitude": float(r["lon"]) if r.get("lon") else None,
            "osm_id": r.get("osm_id"),
        }
        for r in data
    ]
    return {**meta("nominatim", False), "query": query, "results": results}


async def find_nearby_places(
    latitude: float, longitude: float, category: str = "restaurant", radius_m: int = 2000, limit: int = 8
) -> dict:
    """Nearby POIs by category via Overpass (OpenStreetMap)."""
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — synthetic nearby places",
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
    node_filter = OVERPASS_FILTERS.get(category.lower())
    if node_filter is None:
        return {
            "status": "error",
            "error": f"unknown category '{category}'; supported: {sorted(OVERPASS_FILTERS)}",
        }
    query = f"""
    [out:json][timeout:20];
    {node_filter}(around:{radius_m},{latitude},{longitude});
    out center {limit};
    """
    try:
        data = await overpass_query(query)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"nearby search failed: {exc}"}

    results = []
    for el in data.get("elements", [])[:limit]:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        results.append(
            {
                "name": el.get("tags", {}).get("name", "(unnamed)"),
                "category": category,
                "latitude": lat,
                "longitude": lng,
                "distance_km": round(
                    _haversine_km(latitude, longitude, lat, lng), 2
                )
                if lat is not None
                else None,
            }
        )
    return {
        **meta("overpass", False),
        "query": {"latitude": latitude, "longitude": longitude, "category": category},
        "results": results,
    }


async def get_place_details(osm_id: int) -> dict:
    """Details for a single OSM object (Nominatim lookup)."""
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — synthetic place details",
            "osm_id": osm_id,
            "name": f"Demo place {osm_id}",
            "display_name": "Demo location",
            "latitude": 15.2993,
            "longitude": 74.124,
            "address": {},
        }
    try:
        resp = await get_client().get(
            f"{NOMINATIM_URL}/lookup",
            params={"osm_ids": f"N{osm_id}", "format": "jsonv2", "addressdetails": 1},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"place details failed: {exc}"}
    if not data:
        return {"status": "error", "error": f"osm node {osm_id} not found"}
    r = data[0]
    return {
        **meta("nominatim", False),
        "osm_id": osm_id,
        "name": r.get("name") or r.get("display_name", ""),
        "display_name": r.get("display_name"),
        "latitude": float(r["lat"]) if r.get("lat") else None,
        "longitude": float(r["lon"]) if r.get("lon") else None,
        "address": r.get("address", {}),
    }


async def find_nearby_destinations(
    latitude: float, longitude: float, exclude: str = "", radius_km: int = 40, limit: int = 8
) -> dict:
    """Real towns/villages around a destination — day-trip candidates.

    Queries OpenStreetMap place nodes (towns first, then villages), excludes
    the destination itself, sorts by distance, and keeps the most viable
    day-trip candidates.
    """
    exclude_lower = (exclude or "").strip().lower()
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — synthetic nearby destinations",
            "query": {"latitude": latitude, "longitude": longitude, "exclude": exclude},
            "results": [
                {
                    "name": f"Demo Hill Station {i + 1}",
                    "place_type": "town",
                    "latitude": latitude + 0.08 * i,
                    "longitude": longitude + 0.06 * i,
                    "distance_km": round(12.0 * (i + 1), 1),
                    "population": 15000 - i * 2000,
                }
                for i in range(3)
            ],
        }
    query = f"""
    [out:json][timeout:25];
    (
      node["place"="town"](around:{radius_km * 1000},{latitude},{longitude});
      node["place"="village"](around:{radius_km * 1000},{latitude},{longitude});
    );
    out body {limit * 4};
    """
    try:
        data = await overpass_query(query)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"nearby destinations failed: {exc}"}

    results = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip()
        if not name or name.lower() == exclude_lower:
            continue
        lat, lng = el.get("lat"), el.get("lon")
        if lat is None:
            continue
        place_type = tags.get("place", "village")
        population = tags.get("population")
        try:
            population = int(population) if population else None
        except ValueError:
            population = None
        # Hamlets with no population signal are weak day-trip candidates
        if place_type == "village" and (population is None or population < 1500):
            continue
        results.append(
            {
                "name": name,
                "place_type": place_type,
                "latitude": lat,
                "longitude": lng,
                "distance_km": round(_haversine_km(latitude, longitude, lat, lng), 1),
                "population": population,
            }
        )
    # Towns first (more to do), then villages; each group nearest-first
    results.sort(key=lambda r: (0 if r["place_type"] == "town" else 1, r["distance_km"]))
    return {
        **meta("overpass", False),
        "query": {"latitude": latitude, "longitude": longitude, "exclude": exclude},
        "results": results[:limit],
    }
