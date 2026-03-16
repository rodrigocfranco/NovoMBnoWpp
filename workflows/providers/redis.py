"""Redis async client singleton."""

import redis.asyncio as aioredis
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Get async Redis client singleton (connection pool managed internally)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client
