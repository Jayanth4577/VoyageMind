"""MCP client — the ONLY bridge from the backend to the Travel MCP Gateway.

Speaks the MCP streamable-HTTP protocol. Every failure degrades to a structured
"unavailable" response so callers can fall back to cache/mock (spec §25).
"""
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _gateway_url() -> str:
    base = settings.travel_mcp_url.rstrip("/")
    return base if base.endswith("/mcp") else f"{base}/mcp"


def _unwrap_structured(payload: dict) -> dict:
    """FastMCP wraps structured tool output as {"result": ...}; unwrap if present."""
    if set(payload.keys()) == {"result"} and isinstance(payload["result"], dict):
        return payload["result"]
    return payload


class TravelMCPClient:
    """Per-call MCP session over streamable HTTP (stateless gateway, cheap handshake)."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or _gateway_url()

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        try:
            async with streamable_http_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments or {})
        except Exception as exc:  # noqa: BLE001 — degradation is the contract
            logger.warning("MCP call_tool(%s) unavailable: %s", name, exc)
            return {"status": "unavailable", "error": str(exc), "is_mock": True}

        if getattr(result, "isError", False):
            return {"status": "error", "error": "tool reported failure", "is_mock": True}

        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict) and structured:
            return _unwrap_structured(structured)

        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                try:
                    return _unwrap_structured(json.loads(text))
                except (json.JSONDecodeError, TypeError):
                    return {"raw": text}
        return {"status": "error", "error": "empty tool response"}

    async def list_tools(self) -> list[str]:
        try:
            async with streamable_http_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
            return [t.name for t in result.tools]
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP list_tools unavailable: %s", exc)
            return []
