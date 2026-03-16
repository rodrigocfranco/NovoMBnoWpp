"""Session cache manager using Redis."""

import json
from typing import Any

import structlog

from workflows.utils.deduplication import _get_redis_client

logger = structlog.get_logger(__name__)

SESSION_KEY_PREFIX = "session"
SESSION_TTL_SECONDS = 3600  # 1 hour


class CacheManager:
    """Redis-backed session cache for user identification and context."""

    @staticmethod
    async def cache_session(user_id: str, data: dict[str, Any]) -> None:
        """Cache session data with key ``session:{user_id}``, TTL 1h."""
        client = _get_redis_client()
        key = f"{SESSION_KEY_PREFIX}:{user_id}"
        try:
            await client.set(key, json.dumps(data), ex=SESSION_TTL_SECONDS)
        except Exception:
            logger.exception("session_cache_write_error", user_id=user_id)

    @staticmethod
    async def get_session(user_id: str) -> dict[str, Any] | None:
        """Get cached session data. Returns None on miss or error."""
        client = _get_redis_client()
        key = f"{SESSION_KEY_PREFIX}:{user_id}"
        try:
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.exception("session_cache_read_error", user_id=user_id)
            return None

    @staticmethod
    async def invalidate_session(user_id: str) -> None:
        """Remove cached session data."""
        client = _get_redis_client()
        key = f"{SESSION_KEY_PREFIX}:{user_id}"
        try:
            await client.delete(key)
        except Exception:
            logger.exception("session_cache_invalidate_error", user_id=user_id)
