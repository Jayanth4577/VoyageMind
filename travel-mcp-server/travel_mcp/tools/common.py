"""Shared gateway helpers: HTTP client, demo mode, timestamped responses."""
import os
from datetime import UTC, datetime

import httpx

USER_AGENT = "VoyageMind-TravelMCP/0.1 (travel planning workspace)"

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Shared async HTTP client with conservative timeouts."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    return _client


def is_demo_mode() -> bool:
    return os.environ.get("TRAVEL_MCP_DEMO_MODE", "").strip() in ("1", "true", "yes")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def meta(source: str, is_mock: bool) -> dict:
    """Source-transparency metadata attached to every tool response (spec §31)."""
    return {"source": source, "retrieved_at": now_iso(), "is_mock": is_mock}
