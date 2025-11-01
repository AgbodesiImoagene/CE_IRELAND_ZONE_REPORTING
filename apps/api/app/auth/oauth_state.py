"""OAuth state parameter management for CSRF protection."""

from __future__ import annotations

import secrets

import redis.asyncio as aioredis

from app.core.config import settings

# State expires after 10 minutes (OAuth flows should complete quickly)
STATE_TTL_SECONDS = 600


async def get_redis_client() -> aioredis.Redis:
    """Get Redis client connection with instrumentation."""
    from app.core.redis_instrumentation import InstrumentedRedis

    redis_client = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    # Wrap with instrumentation
    return InstrumentedRedis(redis_client)  # type: ignore[return-value]


async def generate_and_store_state(provider: str) -> str:
    """
    Generate a cryptographically secure state token and store it in Redis.

    Args:
        provider: OAuth provider name (e.g., 'google', 'facebook')

    Returns:
        State token string
    """
    # Generate a secure random token
    state = secrets.token_urlsafe(32)

    # Store in Redis with TTL
    redis_client = await get_redis_client()
    key = f"oauth:state:{provider}:{state}"

    try:
        await redis_client.setex(
            key,
            STATE_TTL_SECONDS,
            "1",  # Value doesn't matter, just need the key to exist
        )
    finally:
        await redis_client.aclose()

    return state


async def validate_and_consume_state(provider: str, state: str) -> bool:
    """
    Validate state token and consume it (delete from Redis).

    This ensures each state token can only be used once, preventing replay attacks.

    Args:
        provider: OAuth provider name
        state: State token from OAuth callback

    Returns:
        True if state is valid and was consumed, False otherwise
    """
    if not state:
        return False

    redis_client = await get_redis_client()
    key = f"oauth:state:{provider}:{state}"

    try:
        # Check if state exists
        exists = await redis_client.exists(key)
        if not exists:
            return False

        # Consume (delete) the state token
        await redis_client.delete(key)
        return True
    finally:
        await redis_client.aclose()
