"""Travel MCP Gateway entrypoint.

Exposes the domain tool surface (spec §10/§12) over the MCP streamable-HTTP
transport. External API complexity lives behind these tools; agents never call
third-party endpoints directly.

Tools return a `meta` block ({source, retrieved_at, is_mock}) on every response
for source transparency. Set TRAVEL_MCP_DEMO_MODE=1 to serve labeled synthetic
data without any external calls (demo/CI mode).
"""
from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse

from travel_mcp.tools import maps, transport, weather

mcp = MCPServer(
    name="travel-mcp",
    title="VoyageMind Travel MCP Gateway",
    description="Domain-level travel tools: weather, maps, places, transport, stays, FX, web search",
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok", "service": "travel-mcp"})


@mcp.tool()
def ping() -> dict:
    """Liveness probe exposed as a tool for agent-side smoke tests."""
    return {"status": "ok", "service": "travel-mcp"}


@mcp.tool()
async def get_weather(latitude: float, longitude: float, days: int = 5) -> dict:
    """Multi-day forecast: temperature, precipitation, rain probability, air quality."""
    return await weather.get_weather(latitude, longitude, days)


@mcp.tool()
async def geocode_place(name: str) -> dict:
    """Resolve a place name to coordinates."""
    return await maps.geocode_place(name)


@mcp.tool()
async def calculate_route(points: list[dict]) -> dict:
    """Road distance/duration for an ordered list of {latitude, longitude} points."""
    return await maps.calculate_route(points)


@mcp.tool()
async def optimize_route(points: list[dict]) -> dict:
    """Recommended visiting order (indices into the input list) for a day's points."""
    return await maps.optimize_route(points)


@mcp.tool()
async def search_places(query: str, count: int = 5) -> dict:
    """Free-text place search (name, category, coordinates)."""
    return await maps.search_places(query, count)


@mcp.tool()
async def find_nearby_places(
    latitude: float, longitude: float, category: str = "restaurant", radius_m: int = 2000
) -> dict:
    """Nearby POIs by category: restaurant, cafe, museum, attraction, hotel, supermarket, pharmacy."""
    return await maps.find_nearby_places(latitude, longitude, category, radius_m)


@mcp.tool()
async def get_place_details(osm_id: int) -> dict:
    """Details for a place by its OpenStreetMap node id."""
    return await maps.get_place_details(osm_id)


@mcp.tool()
async def search_transport(origin: str, destination: str, date: str) -> dict:
    """Flight offers between IATA airport codes on a date (YYYY-MM-DD)."""
    return await transport.search_transport(origin, destination, date)


@mcp.tool()
async def search_stays(
    location: str, check_in: str, check_out: str, guests: int = 2
) -> dict:
    """Accommodation options for a location and date range."""
    return await transport.search_stays(location, check_in, check_out, guests)


@mcp.tool()
async def get_exchange_rate(base: str, target: str) -> dict:
    """Current exchange rate between two currency codes (e.g. USD -> INR)."""
    return await transport.get_exchange_rate(base, target)


@mcp.tool()
async def web_search(query: str) -> dict:
    """Web search for events, closures, advisories, festivals (needs a configured provider)."""
    return await transport.web_search(query)


def build_app():
    return mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")


app = build_app()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
