"""Cache service using Redis with graceful degradation.

Provides TTL-based caching for expensive operations (RAG queries, API calls).
Falls back gracefully if Redis is unavailable (logs warning, continues without cache).
"""

import hashlib
import json
from typing import Any

import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

# Redis client (lazy initialization)
_redis_client = None
_redis_available = None


def _get_redis_client():
    """Get Redis client with lazy initialization and availability check."""
    global _redis_client, _redis_available

    # Return cached result if already checked
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    # Try to initialize Redis
    try:
        import redis

        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            logger.warning("redis_not_configured", message="REDIS_URL not set, cache disabled")
            _redis_available = False
            return None

        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )

        # Test connection
        _redis_client.ping()
        logger.info("redis_connected", url=redis_url.split("@")[-1])  # Hide credentials
        _redis_available = True
        return _redis_client

    except ImportError:
        logger.warning(
            "redis_not_installed",
            message="redis-py not installed, cache disabled. Install: pip install redis",
        )
        _redis_available = False
        return None
    except Exception as e:
        logger.warning(
            "redis_connection_failed",
            error_type=type(e).__name__,
            error=str(e),
            message="Cache disabled",
        )
        _redis_available = False
        return None


def _make_cache_key(namespace: str, key: str) -> str:
    """Generate cache key with namespace and hash for long keys.

    Format: namespace:hash(key)[:16]

    Args:
        namespace: Cache namespace (e.g., "rag", "drug_lookup")
        key: Raw key (query, drug name, etc)

    Returns:
        Cache key safe for Redis
    """
    # Hash key to keep it short and safe
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"{namespace}:{key_hash}"


async def get(namespace: str, key: str) -> Any | None:
    """Get value from cache.

    Args:
        namespace: Cache namespace (e.g., "rag", "drug_lookup")
        key: Cache key (query, drug name, etc)

    Returns:
        Cached value (deserialized from JSON) or None if miss/error
    """
    client = _get_redis_client()
    if client is None:
        return None

    try:
        cache_key = _make_cache_key(namespace, key)
        value = client.get(cache_key)

        if value is None:
            logger.debug("cache_miss", namespace=namespace, key=key[:50])
            return None

        logger.info("cache_hit", namespace=namespace, key=key[:50])
        return json.loads(value)

    except Exception as e:
        logger.warning(
            "cache_get_error",
            namespace=namespace,
            error_type=type(e).__name__,
            error=str(e),
        )
        return None


async def set(namespace: str, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Set value in cache with TTL.

    Args:
        namespace: Cache namespace (e.g., "rag", "drug_lookup")
        key: Cache key (query, drug name, etc)
        value: Value to cache (must be JSON-serializable)
        ttl_seconds: Time-to-live in seconds (default 1h)

    Returns:
        True if cached successfully, False otherwise
    """
    client = _get_redis_client()
    if client is None:
        return False

    try:
        cache_key = _make_cache_key(namespace, key)
        serialized = json.dumps(value)

        client.setex(cache_key, ttl_seconds, serialized)
        logger.debug(
            "cache_set",
            namespace=namespace,
            key=key[:50],
            ttl_seconds=ttl_seconds,
            size_bytes=len(serialized),
        )
        return True

    except Exception as e:
        logger.warning(
            "cache_set_error",
            namespace=namespace,
            error_type=type(e).__name__,
            error=str(e),
        )
        return False


async def invalidate(namespace: str, key: str) -> bool:
    """Invalidate (delete) cache entry.

    Args:
        namespace: Cache namespace
        key: Cache key

    Returns:
        True if deleted, False otherwise
    """
    client = _get_redis_client()
    if client is None:
        return False

    try:
        cache_key = _make_cache_key(namespace, key)
        deleted = client.delete(cache_key)
        logger.debug("cache_invalidated", namespace=namespace, key=key[:50], deleted=deleted)
        return deleted > 0

    except Exception as e:
        logger.warning(
            "cache_invalidate_error",
            namespace=namespace,
            error_type=type(e).__name__,
            error=str(e),
        )
        return False


async def clear_namespace(namespace: str) -> int:
    """Clear all keys in a namespace (expensive operation, use sparingly).

    Args:
        namespace: Cache namespace to clear

    Returns:
        Number of keys deleted
    """
    client = _get_redis_client()
    if client is None:
        return 0

    try:
        pattern = f"{namespace}:*"
        keys = client.keys(pattern)
        if not keys:
            return 0

        deleted = client.delete(*keys)
        logger.info("cache_namespace_cleared", namespace=namespace, keys_deleted=deleted)
        return deleted

    except Exception as e:
        logger.warning(
            "cache_clear_error",
            namespace=namespace,
            error_type=type(e).__name__,
            error=str(e),
        )
        return 0
