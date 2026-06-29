"""Redis-based daily budget tracking for tier spend.

All functions degrade gracefully — Redis errors are caught and logged,
never raised. The caller must never crash due to Redis being unavailable.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# TTL for budget keys: 48 hours (enough to survive a day boundary)
_BUDGET_TTL_SECONDS: int = 172800

# ── Redis client ───────────────────────────────────────────────

_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create the async Redis client.

    Returns:
        An async Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection if open."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# ── Key helpers ────────────────────────────────────────────────


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD in UTC."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _budget_key(tier_id: str) -> str:
    """Build a Redis key for a tier's daily budget.

    Args:
        tier_id: The tier identifier.

    Returns:
        A Redis key in the format 'budget:{tier_id}:{YYYY-MM-DD}'.
    """
    return f"budget:{tier_id}:{_today_str()}"


# ── Public functions ───────────────────────────────────────────


async def get_daily_spend(tier_id: str) -> float:
    """Get the current daily spend for a tier.

    Args:
        tier_id: The tier identifier.

    Returns:
        The current daily spend in USD. Returns 0.0 if the key
        does not exist or Redis is unavailable.
    """
    try:
        client = await get_redis_client()
        value = await client.get(_budget_key(tier_id))
        if value is None:
            return 0.0
        return float(value)
    except redis.RedisError as e:
        logger.warning("Redis unavailable: %s", e)
        return 0.0


async def add_spend(tier_id: str, usd_amount: float) -> None:
    """Add spend to a tier's daily budget.

    Uses INCRBYFLOAT for atomic increment. Sets a 48-hour TTL on
    first write to auto-expire old budget keys.

    Args:
        tier_id: The tier identifier.
        usd_amount: The USD amount to add.
    """
    try:
        client = await get_redis_client()
        key = _budget_key(tier_id)

        # Check if key exists before incrementing (for TTL setting)
        exists = await client.exists(key)

        await client.incrbyfloat(key, usd_amount)

        # Set TTL only on first write
        if not exists:
            await client.expire(key, _BUDGET_TTL_SECONDS)

        logger.debug(
            "Added $%.4f spend to tier '%s' (key: %s)", usd_amount, tier_id, key
        )
    except redis.RedisError as e:
        logger.warning("Redis unavailable: %s", e)


async def get_all_today() -> dict[str, float]:
    """Get all daily spend data for today.

    Scans for all budget keys matching today's date and returns
    a mapping of tier_id to current spend.

    Returns:
        Dict mapping tier_id to spend in USD. Returns empty dict
        if Redis is unavailable.
    """
    try:
        client = await get_redis_client()
        today = _today_str()
        pattern = f"budget:*:{today}"

        result: dict[str, float] = {}
        async for key in client.scan_iter(match=pattern):
            # Extract tier_id from key: "budget:{tier_id}:{date}"
            parts = key.split(":")
            if len(parts) >= 3:
                tier_id = ":".join(parts[1:-1])  # Handle tier IDs with colons
                value = await client.get(key)
                if value is not None:
                    result[tier_id] = float(value)

        return result
    except redis.RedisError as e:
        logger.warning("Redis unavailable: %s", e)
        return {}


async def ping() -> bool:
    """Check if Redis is reachable.

    Returns:
        True if Redis responds to PING, False otherwise.
    """
    try:
        client = await get_redis_client()
        return await client.ping()
    except redis.RedisError as e:
        logger.warning("Redis unavailable: %s", e)
        return False
