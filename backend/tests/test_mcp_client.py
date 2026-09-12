"""Integration: real MCP protocol round-trip against the in-process gateway.

Runs the actual Travel MCP Gateway (demo mode) under uvicorn on an ephemeral
port and exercises the backend's TravelMCPClient through the wire format.
Skipped when the travel-mcp-server package is not installed.
"""
import asyncio

import pytest

uvicorn = pytest.importorskip("uvicorn")
gateway = pytest.importorskip("travel_mcp.server")


def test_mcp_protocol_roundtrip(monkeypatch):
    monkeypatch.setenv("TRAVEL_MCP_DEMO_MODE", "1")
    from app.mcp.client import TravelMCPClient

    async def scenario():
        config = uvicorn.Config(gateway.app, host="127.0.0.1", port=0, log_level="error")
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.05)
        assert server.started, "gateway did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        try:
            client = TravelMCPClient(f"http://127.0.0.1:{port}/mcp")

            tools = await client.list_tools()
            assert "get_weather" in tools
            assert "calculate_route" in tools

            ping = await client.call_tool("ping")
            assert ping["status"] == "ok"

            wx = await client.call_tool(
                "get_weather", {"latitude": 15.3, "longitude": 74.1, "days": 3}
            )
            assert wx["is_mock"] is True  # demo mode, clearly labeled
            assert len(wx["daily"]) == 3

            route = await client.call_tool(
                "calculate_route",
                {
                    "points": [
                        {"latitude": 15.5, "longitude": 73.75},
                        {"latitude": 15.29, "longitude": 73.96},
                    ]
                },
            )
            assert route["is_mock"] is True
            assert route["distance_km"] > 0
        finally:
            server.should_exit = True
            await task

    asyncio.run(scenario())


def test_client_degrades_when_gateway_down():
    from app.mcp.client import TravelMCPClient

    async def scenario():
        client = TravelMCPClient("http://127.0.0.1:9/mcp")  # nothing listens here
        out = await client.call_tool("ping")
        assert out["status"] == "unavailable"
        assert await client.list_tools() == []

    asyncio.run(scenario())
