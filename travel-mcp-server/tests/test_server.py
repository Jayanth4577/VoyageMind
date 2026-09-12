"""Tool-registration tests against the in-process MCPServer object."""
import pytest

from travel_mcp.server import mcp

EXPECTED_TOOLS = {
    "ping",
    "get_weather",
    "geocode_place",
    "calculate_route",
    "search_places",
    "find_nearby_places",
    "get_place_details",
    "search_transport",
    "search_stays",
    "get_exchange_rate",
    "web_search",
}


@pytest.mark.anyio
async def test_all_domain_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert EXPECTED_TOOLS <= names


@pytest.mark.anyio
async def test_ping_via_call_tool():
    result = await mcp.call_tool("ping", {})
    # call_tool returns (content, structured) or a result object depending on API
    payload = result[1] if isinstance(result, tuple) else result
    text = str(payload)
    assert "ok" in text
