"""Aggregate Travel MCP facade — the single domain surface used by services/agents.

Usage: `from app.mcp.travel_mcp import travel_mcp` then
`await travel_mcp.weather.get_weather(...)`.
"""
from dataclasses import dataclass

from app.mcp.client import TravelMCPClient
from app.mcp.flight_mcp import FlightMCP
from app.mcp.maps_mcp import MapsMCP
from app.mcp.weather_mcp import WeatherMCP


@dataclass
class TravelMCP:
    weather: WeatherMCP
    maps: MapsMCP
    flights: FlightMCP

    def __init__(self, client: TravelMCPClient | None = None) -> None:
        shared = client or TravelMCPClient()
        self.weather = WeatherMCP(shared)
        self.maps = MapsMCP(shared)
        self.flights = FlightMCP(shared)


travel_mcp = TravelMCP()
