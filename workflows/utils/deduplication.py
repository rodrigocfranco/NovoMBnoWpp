"""Message deduplication via Redis."""

import structlog

from workflows.providers.redis import get_redis_client

logger = structlog.get_logger(__name__)

DEDUP_KEY_PREFIX = "msg_processed"
DEDUP_TTL_SECONDS = 3600  # 1 hour

# Backward compat alias for modules that import the private name
_get_redis_client = get_redis_client


async def is_duplicate_message(message_id: str) -> bool:
    """Check if message was already processed. If not, mark it as processed.

    Uses Redis SETNX pattern: key `msg_processed:{message_id}` with TTL 1h.
    Returns True if duplicate (already processed), False if new.
    """
    client = _get_redis_client()
    key = f"{DEDUP_KEY_PREFIX}:{message_id}"
    try:
        was_set = await client.set(key, "1", ex=DEDUP_TTL_SECONDS, nx=True)
        if not was_set:
            logger.info("duplicate_message_ignored", message_id=message_id)
            return True
        return False
    except Exception:
        logger.exception("redis_dedup_error", message_id=message_id)
        return False
