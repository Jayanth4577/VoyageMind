"""Maps tools: geocoding (Open-Meteo/Nominatim), routing (OSRM), places (Overpass)."""
import asyncio
import itertools
import logging
import os
import time

from travel_mcp.tools.common import USER_AGENT, get_client, is_demo_mode, meta
from travel_mcp.tools.weather import _mock_weather  # noqa: F401 (re-exported for tests)

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OSRM_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
# Primary endpoint + public mirrors — overpass-api.de rate-limits some
# datacenter IPs (e.g. Render), so every query walks the list on failure.
OVERPASS_URLS = [
    os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter"),
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


class OverpassUnavailableError(Exception):
    """Every Overpass mirror failed for a query."""


async def _post_overpass(url: str, query: str) -> dict:
    resp = await get_client().post(url, data={"data": query}, timeout=20.0)
    if resp.status_code in (429, 502, 503, 504):
        raise ConnectionError(f"{url} returned {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


async def overpass_query(query: str) -> dict:
    """Race the Overpass mirrors in parallel and return the first success.

    Sequential fallbacks were too slow for datacenter deployments (each cold
    mirror could eat 45 s before the next even started, blowing the MCP
    client's own timeout). Racing keeps worst-case latency at one timeout.
    """
    tasks = {
        asyncio.create_task(_post_overpass(url, query)): url for url in OVERPASS_URLS
    }
    last_error: Exception | None = None
    try:
        for future in asyncio.as_completed(list(tasks)):
            try:
                return await future
            except Exception as exc:  # noqa: BLE001
                last_error = exc
    finally:
        for task in tasks:
            task.cancel()
    if last_error is not None:
        raise OverpassUnavailableError(
            f"all Overpass endpoints failed: {type(last_error).__name__}: {last_error}"
        )
    raise OverpassUnavailableError("all Overpass endpoints failed")

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
        return {
            "status": "error",
            "error": f"nearby search failed: {type(exc).__name__}: {exc}",
        }

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




WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


WIKI_GEOSEARCH_MAX_KM = 10  # MediaWiki hard cap per query


def _wikipedia_geosearch_point(latitude: float, longitude: float, radius_km: int, limit: int) -> list[dict]:
    """One blocking geosearch call (must be <= 10 km). Uses stdlib urllib:
    Wikimedia blocks some HTTP client TLS fingerprints."""
    import json
    import urllib.parse
    import urllib.request

    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{latitude}|{longitude}",
            "gsradius": min(radius_km, WIKI_GEOSEARCH_MAX_KM) * 1000,
            "gslimit": limit,
            "format": "json",
        }
    )
    req = urllib.request.Request(
        f"{WIKIPEDIA_API}?{params}",
        headers={"User-Agent": f"{USER_AGENT} (github.com/Jayanth4577/VoyageMind)"},
    )
    data = None
    for attempt in range(2):  # one retry for transient rate limits
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(5)
                continue
            raise RuntimeError(f"wikipedia api returned {exc.code}") from exc
    if data is None:
        raise RuntimeError("wikipedia api unavailable")
    if "error" in data:
        api_error = data["error"]
        raise RuntimeError(
            f"wikipedia api error {api_error.get('code')}: {api_error.get('info')}"
        )
    return (data.get("query") or {}).get("geosearch", [])


def _wikipedia_geosearch_sync(latitude: float, longitude: float, radius_km: int, limit: int) -> dict:
    """Blocking Wikipedia geosearch over a wide area via a 9-point grid.

    The API caps each query at 10 km, so wide sweeps tile the area: the
    center plus 8 compass offsets, deduplicated by title.
    """
    raw: list[dict] = []
    wiki_failures: list[str] = []
    points = [(latitude, longitude, radius_km, limit)]
    if radius_km > WIKI_GEOSEARCH_MAX_KM:
        import math

        step = radius_km * 0.7
        for bearing in range(0, 360, 45):
            rad = math.radians(bearing)
            points.append(
                (
                    latitude + step / 111.0 * math.cos(rad),
                    longitude + step / 111.0 * math.sin(rad),
                    WIKI_GEOSEARCH_MAX_KM,
                    max(limit // 2, 3),
                )
            )

    for point_lat, point_lng, point_radius, point_limit in points:
        try:
            raw.extend(
                _wikipedia_geosearch_point(point_lat, point_lng, point_radius, point_limit)
            )
        except Exception as exc:  # noqa: BLE001
            wiki_failures.append(f"{type(exc).__name__}: {exc}")
        time.sleep(1.0)  # pace the grid so Wikipedia's rate limiter stays calm

    if not raw and wiki_failures:
        raise RuntimeError(
            f"wikipedia geosearch failed on all {len(wiki_failures)} grid points; "
            f"first error: {wiki_failures[0]}"
        )

    results = []
    seen: set[str] = set()
    for item in raw:
        title = (item.get("title") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        lat, lon = item.get("lat"), item.get("lon")
        dist_m = item.get("dist")
        results.append(
            {
                "name": title,
                "place_type": "wikipedia",
                "latitude": lat,
                "longitude": lon,
                "distance_km": round((dist_m or 0) / 1000, 1),
                "population": None,
                "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            }
        )
    results.sort(key=lambda r: r["distance_km"])
    return {**meta("wikipedia", False), "results": results[:limit]}


async def wikipedia_geosearch(
    latitude: float, longitude: float, radius_m: int = 40000, limit: int = 10
) -> dict:
    """Notable places around a coordinate via Wikipedia's geosearch API.

    Datacenter-friendly fallback for Overpass: wiki-documented places are a
    good proxy for 'most visited' (forts, lakes, hill stations, towns).
    """
    import asyncio

    return await asyncio.to_thread(
        _wikipedia_geosearch_sync,
        latitude,
        longitude,
        max(1, radius_m // 1000),
        limit,
    )


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
    except OverpassUnavailableError:
        # Datacenter IPs are commonly blocked by Overpass. Fall through
        # SerpAPI Google Maps (if a key is configured — datacenter-friendly
        # and gives the genuinely most-visited places) and then the free
        # Wikipedia geosearch.
        serpapi_key = os.environ.get("SERPAPI_API_KEY", "").strip()
        if serpapi_key:
            serp = await _search_serpapi_nearby(
                latitude, longitude, exclude, serpapi_key
            )
            if serp is not None:
                return serp
        logger.warning(
            "Overpass unavailable for nearby destinations at %s,%s — "
            "trying Wikipedia geosearch fallback",
            latitude,
            longitude,
        )
        try:
            wiki = await wikipedia_geosearch(latitude, longitude, radius_km, limit * 3)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Wikipedia geosearch fallback failed for %s,%s: %s",
                latitude,
                longitude,
                exc,
            )
            return {
                "status": "error",
                "error": f"nearby destinations failed: {type(exc).__name__}: {exc}",
            }
        exclude_lower = exclude.strip().lower()
        wiki_results = []
        for r in wiki.get("results") or []:
            name = (r.get("name") or "").strip()
            if not name or name.lower() == exclude_lower:
                continue  # never suggest the destination as its own day trip
            # ring queries report distance from their own centers — recompute
            # the true distance to the destination
            if r.get("latitude") is not None and r.get("longitude") is not None:
                r["distance_km"] = round(
                    _haversine_km(latitude, longitude, r["latitude"], r["longitude"]), 1
                )
            wiki_results.append(r)
        # Blend: a couple of in-town notables, then actual out-of-town day trips
        near = [r for r in wiki_results if r.get("distance_km", 0) < 5][:2]
        far = [r for r in wiki_results if r.get("distance_km", 0) >= 5][: max(limit - 2, 1)]
        wiki["results"] = near + far
        return wiki

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


async def _search_serpapi_nearby(
    latitude: float, longitude: float, exclude: str, api_key: str
) -> dict | None:
    """Most-visited places around a destination via SerpAPI Google Maps.

    Datacenter-friendly (SerpAPI is built for server use), and the results are
    ranked by real visitation — exactly the 'Panchgani and other famous spots'
    signal. Returns the standard results shape or None to let other fallbacks
    try.
    """
    from travel_mcp.tools.transport import SERPAPI_URL  # reuse the base URL

    try:
        resp = await get_client().get(
            SERPAPI_URL,
            params={
                "engine": "google_maps",
                "type": "search",
                "q": f"tourist attractions near {exclude}",
                "ll": f"@{latitude},{longitude},13z",
                "api_key": api_key,
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("serpapi nearby failed: %s", exc)
        return None

    if data.get("error"):
        logger.warning("serpapi nearby error: %s", str(data["error"])[:200])
        return None

    results = []
    for place in (data.get("local_results") or [])[:10]:
        name = (place.get("title") or "").strip()
        if not name or name.lower() == exclude.strip().lower():
            continue
        gps = place.get("gps_coordinates") or {}
        lat, lng = gps.get("latitude"), gps.get("longitude")
        address = place.get("address") or ""
        results.append(
            {
                "name": name,
                "place_type": (place.get("type") or "attraction").lower().replace(" ", "_"),
                "latitude": lat,
                "longitude": lng,
                "distance_km": round(
                    _haversine_km(latitude, longitude, lat, lng), 1
                )
                if lat is not None and lng is not None
                else None,
                "population": None,
                "rating": place.get("rating"),
                "address": address,
            }
        )
    if not results:
        return None
    results.sort(key=lambda r: r["distance_km"] if r["distance_km"] is not None else 9999)
    return {
        **meta("serpapi", False),
        "query": {"latitude": latitude, "longitude": longitude, "exclude": exclude},
        "results": results,
    }
