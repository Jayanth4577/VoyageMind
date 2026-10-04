"""Transport & stay tools: SerpApi Google Flights or labeled demo, FX rates, web search."""
import os
import re

from travel_mcp.tools.common import get_client, is_demo_mode, meta
from travel_mcp.tools.maps import _haversine_km  # shared geo math

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
    response = {
        **meta("mock", True),
        "note": "DEMO DATA — synthetic flights; configure SERPAPI_API_KEY for real offers",
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
    if _to_iata(destination) != destination.strip().upper():
        route_options = _route_options_for(
            origin, destination, date, response["offers"], "INR"
        )
        if route_options:
            response["route_options"] = route_options
    return response


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


SERPAPI_URL = "https://serpapi.com/search.json"


def _parse_amount(value) -> float | None:
    """SerpAPI returns prices as formatted strings ('₹7,813'); extract the number."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    digits = re.sub(r"[^0-9.]", "", str(value))
    return float(digits) if digits else None

# Destinations without their own airport -> the practical airport people use
_NEAREST_AIRPORT = {
    "MAHABALESHWAR": "PNQ",
    "MAHABALESHWER": "PNQ",
    "MAHABLESHWAR": "PNQ",
    "PANCHGANI": "PNQ",
    "LONAVALA": "PNQ",
    "KHANDALA": "PNQ",
    "SHIRDI": "SAG",
    "NASHIK": "ISK",
    "NASEEK": "ISK",
    "MANALI": "KUU",
    "SHIMLA": "SLV",
    "MUSSOORIE": "DED",
    "RISHIKESH": "DED",
    "HARIDWAR": "DED",
    "DARJEELING": "IXB",
    "GANGTOK": "IXB",
    "GOKARNA": "GOI",
    "ALLEPPEY": "COK",
    "ALAPPUZHA": "COK",
    "MUNNAR": "COK",
    "KOVALAM": "TRV",
    "OOTY": "CJB",
    "KODAIKANAL": "CJB",
    "COORG": "COK",
    "MADIKERI": "COK",
    "HAMPI": "VDY",
    "AURANGABAD": "IXU",
    "AJANTA": "IXU",
    "ELLORA": "IXU",
    "AMRITSAR": "ATQ",
    "LEH": "IXL",
    "LADAKH": "IXL",
    "SRINAGAR": "SXR",
    "GULMARG": "SXR",
    "PAHALGAM": "SXR",
    "PORT BLAIR": "IXZ",
    "ANDAMAN": "IXZ",
    "UDAIPUR": "UDR",
    "JODHPUR": "JDH",
    "JAISALMER": "JSA",
    "VARANASI": "VNS",
    "KHAJURAHO": "HJR",
    "RAMESWARAM": "IXM",
    "PONDICHERRY": "PNY",
    "PUDUCHERRY": "PNY",
    "MYSORE": "MYQ",
    "MYSURU": "MYQ",
}

_CITY_TO_IATA = {
    "BENGALURU": "BLR",
    "BANGALORE": "BLR",
    "GOA": "GOI",
    "DELHI": "DEL",
    "NEW DELHI": "DEL",
    "MUMBAI": "BOM",
    "BOMBAY": "BOM",
    "CHENNAI": "MAA",
    "MADRAS": "MAA",
    "KOLKATA": "CCU",
    "CALCUTTA": "CCU",
    "HYDERABAD": "HYD",
    "KOCHI": "COK",
    "COCHIN": "COK",
    "AHMEDABAD": "AMD",
    "PUNE": "PNQ",
    "JAIPUR": "JAI",
    "PARIS": "CDG",
    "AUSTIN": "AUS",
    "LONDON": "LHR",
    "NEW YORK": "JFK",
    "SAN FRANCISCO": "SFO",
    "DUBAI": "DXB",
    "SINGAPORE": "SIN",
    "TOKYO": "HND",
    "BANGKOK": "BKK",
}


def _to_iata(val: str) -> str:
    cleaned = (val or "").strip().upper()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned
    if cleaned in _CITY_TO_IATA:
        return _CITY_TO_IATA[cleaned]
    # no airport of its own -> nearest practical airport, if we know one
    return _NEAREST_AIRPORT.get(cleaned, cleaned)


# Airport context for the flight+road combo (city name + approx coords).
_AIRPORT_META = {
    "PNQ": ("Pune", 18.58, 73.92),
    "GOI": ("Goa (Dabolim)", 15.38, 73.83),
    "DED": ("Dehradun", 30.19, 78.18),
    "IXB": ("Bagdogra", 26.68, 88.33),
    "COK": ("Kochi", 10.15, 76.40),
    "CJB": ("Coimbatore", 11.03, 77.04),
    "MYS": ("Mysuru", 12.23, 76.65),
    "VDY": ("Vidyanagar (Hampi)", 15.05, 76.63),
    "IXU": ("Aurangabad", 19.86, 75.40),
    "ATQ": ("Amritsar", 31.71, 74.80),
    "IXL": ("Leh", 34.14, 77.55),
    "SXR": ("Srinagar", 33.99, 74.77),
    "IXZ": ("Port Blair", 11.64, 92.73),
    "TRV": ("Trivandrum", 8.48, 76.92),
    "KGM": ("Kathgodam", 29.35, 79.53),
    "ABR": ("Abu Road", 24.59, 72.78),
    "GOKA": ("Gokarna", 14.55, 74.31),
}

# Nearest practical railhead per no-airport destination (factual reference;
# fares are NOT invented — the card links to IRCTC to check them).
_NEAREST_RAILWAY = {
    "MAHABALESHWAR": ("WATHAR", "Wathar (nearest railhead)"),
    "MAHABALESHWER": ("WATHAR", "Wathar (nearest railhead)"),
    "MAHABLESHWAR": ("WATHAR", "Wathar (nearest railhead)"),
    "PANCHGANI": ("WATHAR", "Wathar (nearest railhead)"),
    "MANALI": ("CDG", "Chandigarh (~250 km)"),
    "MUSSOORIE": ("DDN", "Dehradun (~35 km)"),
    "RISHIKESH": ("RKSH", "Rishikesh (direct)"),
    "HARIDWAR": ("HW", "Haridwar (direct)"),
    "DARJEELING": ("NJP", "New Jalpaiguri (~70 km)"),
    "GOKARNA": ("GOKA", "Gokarna Road (~10 km)"),
    "OOTY": ("MTP", "Mettupalayam (~40 km, Nilgiri Mountain Railway)"),
    "KODAIKANAL": ("KQZ", "Kodaikanal Road (~80 km)"),
    "COORG": ("MYS", "Mysuru (~95 km)"),
    "MADIKERI": ("MYS", "Mysuru (~95 km)"),
    "HAMPI": ("HPT", "Hosapete (~13 km)"),
    "SHIMLA": ("KLK", "Kalka (~90 km, heritage toy train)"),
    "NAINITAL": ("KGM", "Kathgodam (~35 km)"),
    "MOUNT ABU": ("ABR", "Abu Road (~28 km)"),
    "UDAIPUR": ("UDZ", "Udaipur City (direct)"),
    "VARANASI": ("BSB", "Varanasi Jn (direct)"),
    "JODHPUR": ("JU", "Jodhpur (direct)"),
    "JAISALMER": ("JSM", "Jaisalmer (direct)"),
    "KHAJURAHO": ("KURJ", "Khajuraho (direct)"),
    "RAMESWARAM": ("RMM", "Rameswaram (direct)"),
    "PONDICHERRY": ("PDY", "Puducherry (direct)"),
    "PUDUCHERRY": ("PDY", "Puducherry (direct)"),
    "MYSORE": ("MYS", "Mysuru (direct)"),
    "MYSURU": ("MYS", "Mysuru (direct)"),
    "AURANGABAD": ("AWB", "Aurangabad (direct)"),
    "AJANTA": ("AWB", "Aurangabad (direct)"),
    "ELLORA": ("AWB", "Aurangabad (direct)"),
}


def _road_estimate(lat1, lng1, lat2, lng2):
    """Approximate road leg from straight-line distance (labeled as estimate)."""
    km = round(_haversine_km(lat1, lng1, lat2, lng2) * 1.3, 0)
    hours = round(km / 35.0, 1)  # conservative for ghat/state roads
    return int(km), hours


def _route_options_for(origin: str, destination: str, date: str, offers: list, currency: str) -> list:
    """Multimodal route suggestions when the destination has no airport:
    fly-to-nearest + road, train to the nearest railhead, or a direct bus.
    Flight prices are live; bus/train fares are not available via free APIs,
    so those cards link out to the bookers instead of inventing numbers."""
    dest_code = _to_iata(destination)
    if destination.strip().upper() not in _NEAREST_AIRPORT:
        return []  # destination has a real airport; plain flights suffice

    options = []

    best = next((o for o in offers if (o.get("price") or 0) > 0), None)
    if best is not None:
        options.append(
            {
                "mode": "flight_road",
                "title": f"Fly {origin} → {_AIRPORT_META.get(dest_code, (dest_code,))[0]}, then road to {destination.title()}",
                "flight_price": best.get("price"),
                "currency": currency,
                "airline": best.get("airline"),
                "links": {
                    "flight": (
                        "https://www.google.com/travel/flights?q="
                        + f"flights+from+{origin}+to+{_AIRPORT_META.get(dest_code, (dest_code,))[0]}+on+{date}".replace(" ", "+")
                    ),
                    "bus": (
                        f"https://www.redbus.in/search?fromCityName={_AIRPORT_META.get(dest_code, (dest_code,))[0]}"
                        f"&toCityName={destination}&doj={date[8:]}-{date[5:7]}-{date[:4]}"
                    ),
                },
            }
        )

    rail = _NEAREST_RAILWAY.get(destination.strip().upper())
    if rail:
        _station_code, station_label = rail
        options.append(
            {
                "mode": "train",
                "title": f"Train {origin} → {station_label}",
                "links": {"train": "https://www.irctc.co.in/nget/train/search"},
            }
        )

    options.append(
        {
            "mode": "bus",
            "title": f"Direct bus {origin} → {destination.title()}",
            "links": {
                "bus": (
                    f"https://www.redbus.in/search?fromCityName={origin}"
                    f"&toCityName={destination}&doj={date[8:]}-{date[5:7]}-{date[:4]}"
                )
            },
        }
    )
    return options


async def _search_serpapi_flights(
    origin: str, destination: str, date: str, api_key: str, adults: int = 1
) -> dict | None:
    """Fetch live flight offers from SerpApi Google Flights."""
    dep_iata = _to_iata(origin)
    arr_iata = _to_iata(destination)

    try:
        resp = await get_client().get(
            SERPAPI_URL,
            params={
                "engine": "google_flights",
                "departure_id": dep_iata,
                "arrival_id": arr_iata,
                "outbound_date": date,
                "currency": "INR",
                "type": "2",  # One-way
                "adults": max(1, adults),
                "api_key": api_key,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None

    raw_flights = data.get("best_flights", []) + data.get("other_flights", [])
    if not raw_flights:
        return None

    offers = []
    for item in raw_flights[:10]:
        legs = item.get("flights", [])
        if not legs:
            continue
        first_leg = legs[0]
        last_leg = legs[-1]
        airline = first_leg.get("airline") or item.get("airline") or "Airline"
        flight_no = first_leg.get("flight_number") or ""
        dep_time = (first_leg.get("departure_airport") or {}).get("time", "")
        arr_time = (last_leg.get("arrival_airport") or {}).get("time", "")

        offers.append({
            "id": flight_no or f"serp-{len(offers) + 1}",
            "airline": f"{airline} ({flight_no})" if flight_no else airline,
            "departure_at": (
                dep_time.replace(" ", "T") + ":00"
                if dep_time and "T" not in dep_time
                else dep_time
            ),
            "arrival_at": (
                arr_time.replace(" ", "T") + ":00"
                if arr_time and "T" not in arr_time
                else arr_time
            ),
            "duration_minutes": item.get("total_duration") or first_leg.get("duration"),
            "price": float(item.get("price") or 0),
            "currency": "INR",
        })

    if not offers:
        return None

    nearest_used = _to_iata(destination) != (destination or "").strip().upper()
    note = None
    if nearest_used and destination:
        note = (
            f"Flights land at the nearest airport ({_to_iata(destination)}) — "
            f"{destination.title()} has none of its own."
        )

    response = {
        **meta("serpapi", False),
        "query": {"origin": origin, "destination": destination, "date": date},
        **({"note": note} if note else {}),
        "offers": offers,
    }
    if nearest_used:
        route_options = _route_options_for(origin, destination, date, offers, "INR")
        if route_options:
            response["route_options"] = route_options
    return response


async def search_transport(
    origin: str, destination: str, date: str, adults: int = 1
) -> dict:
    """Flight offers for an origin/destination pair on a date (SerpApi Google Flights or labeled mock)."""
    if is_demo_mode():
        return _mock_transport(origin, destination, date)

    # 1. Try SerpApi (Google Flights) if configured
    serpapi_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if serpapi_key:
        serp_result = await _search_serpapi_flights(
            origin, destination, date, serpapi_key, adults=adults
        )
        if serp_result:
            return serp_result

    # 2. Transparent fallback to realistic physics-based mock transport
    return _mock_transport(origin, destination, date)


async def _search_serpapi_hotels(
    location: str, check_in: str, check_out: str, guests: int, api_key: str
) -> dict | None:
    """Fetch live hotel offers from SerpApi Google Hotels."""
    try:
        resp = await get_client().get(
            SERPAPI_URL,
            params={
                "engine": "google_hotels",
                "q": f"hotels in {location}",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "adults": max(1, guests),
                "currency": "INR",
                "api_key": api_key,
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None

    properties = data.get("properties", [])
    if not properties:
        return None

    stays = []
    for prop in properties[:10]:
        name = (prop.get("name") or "").strip()
        if not name:
            continue
        rate = (prop.get("rate_per_night") or {}).get("lowest")
        stays.append(
            {
                "id": prop.get("property_id") or f"serp-stay-{len(stays) + 1}",
                "name": name,
                "location_name": prop.get("nearby_places", [{}])[0].get("name", location)
                if prop.get("nearby_places")
                else location,
                "price_per_night": _parse_amount(rate),
                "rating": prop.get("overall_rating"),
                "guests_per_room": max(1, guests),
                "type": prop.get("type"),
                "link": prop.get("link"),
            }
        )

    if not stays:
        return None

    return {
        **meta("serpapi", False),
        "query": {
            "location": location,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
        },
        "stays": stays,
    }


async def search_stays(
    location: str, check_in: str, check_out: str, guests: int = 2
) -> dict:
    """Accommodation search via SerpApi Google Hotels, or labeled demo data."""
    serpapi_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not is_demo_mode() and serpapi_key:
        serp_result = await _search_serpapi_hotels(
            location, check_in, check_out, guests, serpapi_key
        )
        if serp_result:
            return serp_result
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
