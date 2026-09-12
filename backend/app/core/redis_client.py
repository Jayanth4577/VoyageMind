"""Redis cache client with graceful degradation.

Redis is an optimization, never a hard dependency: on connection failure the
helpers no-op (return miss / skip write) and the caller falls back to live APIs
or labeled mock data (spec §25/§26).
"""
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None
_client_failed = False


def get_redis() -> aioredis.Redis | None:
    """Lazily create the client; returns None when Redis is unavailable."""
    global _client, _client_failed
    if _client_failed:
        return None
    if _client is None:
        try:
            _client = aioredis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=1.0
            )
        except Exception as exc:  # pragma: no cover - construction rarely fails
            logger.warning("Redis client construction failed: %s", exc)
            _client_failed = True
            return None
    return _client


async def cache_get_json(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("cache_get_json degraded for key=%s: %s", key, exc)
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    except Exception as exc:
        logger.warning("cache_set_json degraded for key=%s: %s", key, exc)


def reset_redis_state() -> None:
    """Test hook: forget the cached client so a new URL can be probed."""
    global _client, _client_failed
    _client = None
    _client_failed = False
