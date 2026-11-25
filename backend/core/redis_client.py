"""
Async Redis client using redis.asyncio with connection pool and graceful fallback.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Optional[Redis] = None
_memory_fallback: dict[str, str] = {}

KEY_SIGNAL_STATE = "signal:state"
KEY_TRAFFIC_STATE = "signal:traffic:{direction}"
KEY_EMERGENCY_STATE = "emergency:current"
KEY_ESP32_STATUS = "esp32:status"
KEY_SYSTEM_PERF = "system:performance"
KEY_DEMO_MODE = "system:demo_mode"


async def init_redis() -> Optional[Redis]:
    """Initialize Redis connection pool. Falls back cleanly if Redis is unreachable."""
    global _redis_client
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_POOL_SIZE,
        )
        await client.ping()
        _redis_client = client
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception as exc:
        _redis_client = None
        logger.warning("redis_unavailable_using_memory_cache", error=str(exc))
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection pool."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
    logger.info("redis_connection_closed")


def get_redis() -> Optional[Redis]:
    """Return the global Redis client, or None if operating in degraded fallback."""
    return _redis_client


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """Serialize and store a value in Redis (or memory fallback)."""
    serialized = json.dumps(value) if not isinstance(value, str) else value
    client = get_redis()
    if client is None:
        _memory_fallback[key] = serialized
        return
    try:
        if ttl:
            await client.setex(key, ttl, serialized)
        else:
            await client.set(key, serialized)
    except Exception as exc:
        logger.warning("redis_set_failed", key=key, error=str(exc))
        _memory_fallback[key] = serialized


async def cache_get(key: str) -> Optional[Any]:
    """Retrieve and deserialize a value from Redis (or memory fallback)."""
    client = get_redis()
    value: Optional[str] = None
    if client is None:
        value = _memory_fallback.get(key)
    else:
        try:
            value = await client.get(key)
        except Exception as exc:
            logger.warning("redis_get_failed", key=key, error=str(exc))
            value = _memory_fallback.get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


async def cache_delete(key: str) -> None:
    """Delete a key from Redis."""
    _memory_fallback.pop(key, None)
    client = get_redis()
    if client is not None:
        try:
            await client.delete(key)
        except Exception as exc:
            logger.warning("redis_delete_failed", key=key, error=str(exc))


async def cache_set_signal_state(state: dict) -> None:
    await cache_set(KEY_SIGNAL_STATE, state, ttl=300)


async def cache_get_signal_state() -> Optional[dict]:
    return await cache_get(KEY_SIGNAL_STATE)


async def cache_set_traffic_state(direction: str, data: dict) -> None:
    await cache_set(KEY_TRAFFIC_STATE.format(direction=direction), data, ttl=60)


async def cache_get_traffic_state(direction: str) -> Optional[dict]:
    return await cache_get(KEY_TRAFFIC_STATE.format(direction=direction))


async def cache_set_emergency_state(state: Optional[dict]) -> None:
    if state is None:
        await cache_delete(KEY_EMERGENCY_STATE)
    else:
        await cache_set(KEY_EMERGENCY_STATE, state, ttl=600)


async def cache_get_emergency_state() -> Optional[dict]:
    return await cache_get(KEY_EMERGENCY_STATE)


async def publish_event(channel: str, message: dict) -> None:
    client = get_redis()
    if client is not None:
        try:
            await client.publish(channel, json.dumps(message))
        except Exception as exc:
            logger.warning("redis_publish_failed", channel=channel, error=str(exc))


async def health_check() -> bool:
    try:
        client = get_redis()
        if client is None:
            return False
        return bool(await client.ping())
    except Exception:
        return False
