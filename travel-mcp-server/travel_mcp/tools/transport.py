"""Transport & stay tools: Duffel flights (key) or labeled demo, FX rates, web search."""
import os

from travel_mcp.tools.common import get_client, is_demo_mode, meta
from travel_mcp.tools.maps import _haversine_km  # shared geo math

DUFFEL_URL = "https://api.duffel.com"

# Plausible demo IATA pairs for mock generation (never presented as real prices)
_DEMO_AIRPORTS = {
    "BLR": (13.1986, 77.7066),
    "GOI": (15.3808, 73.8314),
    "DEL": (28.5562, 77.1000),
    "BOM": (19.0896, 72.8656),
}


def _mock_transport(origin: str, destination: str, date: str) -> dict:
    o, d = _DEMO_AIRPORTS.get(origin.upper()), _DEMO_AIRPORTS.get(destination.upper())
    km = _haversine_km(*o, *d) if o and d else 800
    minutes = round(km / 750 * 60) + 45  # cruise 750 km/h + taxi time
    base_fare = round(2500 + km * 3.5)
    return {
        **meta("mock", True),
        "note": "DEMO DATA — synthetic flights; connect a Duffel key for real offers",
        "query": {"origin": origin, "destination": destination, "date": date},
        "offers": [
            {
                "id": f"demo-offer-{i + 1}",
                "airline": airline,
                "departure_at": f"{date}T{dep}:00",
                "arrival_at": f"{date}T{arr}:00",
                "duration_minutes": minutes,
                "price": base_fare + i * 700,
                "currency": "INR",
            }
            for i, (airline, dep, arr) in enumerate(
                [("DemoAir", "07:30", f"{7 + minutes // 60:02d}:{minutes % 60:02d}"),
                 ("DemoJet", "14:00", f"{14 + minutes // 60:02d}:{minutes % 60:02d}"),
                 ("DemoWings", "20:15", f"{(20 + minutes // 60) % 24:02d}:{minutes % 60:02d}")]
            )
        ],
    }


def _mock_stays(location: str, check_in: str, check_out: str, guests: int) -> dict:
    nightly = 2200
    return {
        **meta("mock", True),
        "note": "DEMO DATA — synthetic stays; no free provider integrated yet",
        "query": {"location": location, "check_in": check_in, "check_out": check_out, "guests": guests},
        "stays": [
            {
                "id": f"demo-stay-{i + 1}",
                "name": name,
                "location_name": location,
                "price_per_night": nightly + i * 900,
                "rating": round(7.8 + 0.4 * i, 1),
                "guests_per_room": 2,
            }
            for i, name in enumerate(
                ["Demo Beach Guesthouse", "Demo City Hotel", "Demo Boutique Resort"]
            )
        ],
    }


async def search_transport(origin: str, destination: str, date: str) -> dict:
    """Flight offers for an IATA origin/destination pair on a date (Duffel test mode)."""
    api_key = os.environ.get("DUFFEL_API_KEY", "").strip()
    if not api_key:
        return _mock_transport(origin, destination, date)
    try:
        resp = await get_client().post(
            f"{DUFFEL_URL}/air/offer_requests?return_offers=true",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Duffel-Version": "v2",
                "Accept": "application/json",
            },
            json={
                "data": {
                    "slices": [{"origin": origin.upper(), "destination": destination.upper(), "departure_date": date}],
                    "passengers": [{"type": "adult"}],
                    "cabin_class": "economy",
                }
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"flight search failed: {exc}"}

    offers = []
    for offer in (data.get("data", {}) or {}).get("offers", [])[:10]:
        slices = offer.get("slices", [{}])
        segs = slices[0].get("segments", [{}])
        offers.append(
            {
                "id": offer.get("id"),
                "airline": (offer.get("owner") or {}).get("name"),
                "departure_at": segs[0].get("departing_at"),
                "arrival_at": segs[-1].get("arriving_at"),
                "duration_minutes": int(slices[0].get("duration", "PT0S")[2:-1] or 0) // 60
                or None,
                "price": float(offer.get("total_amount") or 0),
                "currency": offer.get("total_currency", "USD"),
            }
        )
    return {
        **meta("duffel", False),
        "query": {"origin": origin, "destination": destination, "date": date},
        "offers": offers,
    }


async def search_stays(
    location: str, check_in: str, check_out: str, guests: int = 2
) -> dict:
    """Accommodation search. Provider is replaceable; demo data until one is configured."""
    # No free global stays API exists; keep the interface, return labeled demo data.
    return _mock_stays(location, check_in, check_out, guests)


async def get_exchange_rate(base: str, target: str) -> dict:
    """Current exchange rate (open.er-api.com, no key)."""
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — fixed demo rate",
            "base": base.upper(),
            "target": target.upper(),
            "rate": 83.0,
        }
    try:
        resp = await get_client().get(f"https://open.er-api.com/v6/latest/{base.upper()}")
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"exchange-rate lookup failed: {exc}"}
    rates = data.get("rates", {})
    target_upper = target.upper()
    if target_upper not in rates:
        return {"status": "error", "error": f"unknown currency '{target}'"}
    return {
        **meta("open-er-api", False),
        "base": base.upper(),
        "target": target_upper,
        "rate": rates[target_upper],
    }


async def web_search(query: str, count: int = 5) -> dict:
    """Web search for events/closures/advisories. Requires a Tavily-compatible key.

    Returns an honest 'no_provider' response rather than fabricated results —
    the system must never invent live information (spec principle 10).
    """
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if is_demo_mode():
        return {
            **meta("mock", True),
            "note": "DEMO DATA — synthetic search results",
            "query": query,
            "results": [
                {"title": f"Demo result {i + 1}", "url": "https://example.com", "snippet": "Demo snippet"}
                for i in range(count)
            ],
        }
    if not api_key:
        return {
            "status": "no_provider",
            "note": "No search provider configured (set TAVILY_API_KEY); refusing to fabricate results",
            "query": query,
            "results": [],
            **meta("none", True),
        }
    try:
        resp = await get_client().post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": count},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"web search failed: {exc}"}
    return {
        **meta("tavily", False),
        "query": query,
        "results": [
            {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content", "")[:200]}
            for r in data.get("results", [])[:count]
        ],
    }
