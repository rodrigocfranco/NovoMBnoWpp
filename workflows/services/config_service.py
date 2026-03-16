"""Configuration service with Redis cache-aside pattern.

TTL 5min with immediate invalidation on admin save.
"""

import json
from typing import Any

import structlog
from redis.exceptions import RedisError

from workflows.models import Config
from workflows.providers.redis import get_redis_client
from workflows.utils.errors import ValidationError

logger = structlog.get_logger(__name__)

CONFIG_CACHE_TTL = 300  # 5 minutos (FR38: mudanças refletidas em até 5 min)
CONFIG_CACHE_PREFIX = "config:"


class ConfigService:
    @staticmethod
    async def get(key: str) -> Any:
        """Fetch config value with Redis cache-aside (TTL 5min).

        1. Check Redis cache
        2. On miss → query DB → populate cache
        3. On Redis error → fallback to DB (graceful degradation)
        """
        cache_key = f"{CONFIG_CACHE_PREFIX}{key}"

        # 1. Try Redis cache first
        try:
            client = get_redis_client()
            cached = await client.get(cache_key)
            if cached is not None:
                logger.debug("config_cache_hit", key=key)
                return json.loads(cached)
            logger.debug("config_cache_miss", key=key)
        except (RedisError, RuntimeError, OSError):
            logger.warning("config_cache_error", key=key, action="fallback_to_db")

        # 2. Cache miss or Redis error → query DB
        try:
            config = await Config.objects.aget(key=key)
        except Config.DoesNotExist:
            raise ValidationError(f"Config not found: {key}", details={"key": key})

        # 3. Populate cache (best-effort)
        try:
            client = get_redis_client()
            await client.setex(cache_key, CONFIG_CACHE_TTL, json.dumps(config.value))
        except (RedisError, RuntimeError, OSError):
            logger.warning("config_cache_set_error", key=key)

        return config.value

    @staticmethod
    async def invalidate(key: str) -> None:
        """Delete config cache key (called on admin save)."""
        cache_key = f"{CONFIG_CACHE_PREFIX}{key}"
        try:
            client = get_redis_client()
            await client.delete(cache_key)
            logger.info("config_cache_invalidated", key=key)
        except (RedisError, RuntimeError, OSError):
            logger.warning("config_cache_invalidate_error", key=key)
