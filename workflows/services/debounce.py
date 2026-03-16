"""Debounce service — accumulates rapid messages via Redis buffer.

Multi-instance safe (Cloud Run) using last-message-wins pattern:
1. Buffer messages in Redis list (RPUSH + EXPIRE atomic pipeline)
2. Set timer key with unique timestamp
3. After sleep(debounce_ttl), check if our timer is still the latest
4. If yes: process batch. If no: skip (newer timer will process).
"""

import asyncio
import json
import time
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from workflows.services.config_service import ConfigService
from workflows.utils.deduplication import _get_redis_client

logger = structlog.get_logger(__name__)

BUFFER_KEY_PREFIX = "msg_buffer"
TIMER_KEY_PREFIX = "msg_timer"
DEFAULT_DEBOUNCE_TTL = 3


async def _get_debounce_ttl() -> int:
    """Get debounce TTL from Config model (default 3s)."""
    try:
        return int(await ConfigService.get("debounce_ttl"))
    except Exception:
        logger.warning("debounce_ttl_config_fallback", default=DEFAULT_DEBOUNCE_TTL)
        return DEFAULT_DEBOUNCE_TTL


async def buffer_message(phone: str, message_data: str, ttl: int) -> None:
    """RPUSH message to Redis buffer with EXPIRE (atomic pipeline)."""
    redis = _get_redis_client()
    key = f"{BUFFER_KEY_PREFIX}:{phone}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.rpush(key, message_data)
        pipe.expire(key, ttl + 5)
        await pipe.execute()
    logger.info("message_buffered", phone=phone)


_LRANGE_AND_DELETE = """
local msgs = redis.call('lrange', KEYS[1], 0, -1)
redis.call('del', KEYS[1])
return msgs
"""


async def get_and_clear_buffer(phone: str) -> list[str]:
    """Atomic LRANGE + DELETE via Lua script (prevents message loss).

    Without atomicity, a RPUSH between LRANGE and DELETE would lose the new
    message. Lua scripts execute atomically in Redis.
    """
    redis = _get_redis_client()
    key = f"{BUFFER_KEY_PREFIX}:{phone}"
    result = await redis.eval(_LRANGE_AND_DELETE, 1, key)
    return list(result or [])


async def schedule_processing(
    phone: str,
    validated_data: dict[str, Any],
    process_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Buffer message and schedule processing after debounce period.

    Uses last-message-wins pattern for multi-instance safety:
    - Each call sets its own unique timestamp in msg_timer:{phone}
    - After sleep, only the latest timer processes the batch
    """
    debounce_ttl = await _get_debounce_ttl()

    # 1. Buffer the message
    await buffer_message(phone, json.dumps(validated_data), debounce_ttl)

    # 2. Set timer with unique timestamp (multi-instance safe)
    redis = _get_redis_client()
    timer_key = f"{TIMER_KEY_PREFIX}:{phone}"
    my_timestamp = f"{time.time():.9f}:{id(asyncio.current_task())}"
    await redis.set(timer_key, my_timestamp, ex=debounce_ttl + 5)
    logger.info("debounce_timer_set", phone=phone, ttl=debounce_ttl)

    # 3. Sleep for debounce period
    await asyncio.sleep(debounce_ttl)

    # 4. Check if we're the latest timer (last-message-wins)
    current = await redis.get(timer_key)
    if current != my_timestamp:
        logger.debug("debounce_timer_superseded", phone=phone)
        return

    # 5. We're the latest → process the batch
    await redis.delete(timer_key)
    raw_messages = await get_and_clear_buffer(phone)

    if not raw_messages:
        logger.warning("debounce_empty_buffer", phone=phone)
        return

    # Combine messages (skip corrupted entries to avoid losing the entire batch)
    messages: list[dict[str, Any]] = []
    for raw in raw_messages:
        try:
            messages.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            logger.warning("debounce_invalid_buffer_entry", phone=phone, raw=raw[:100])

    if not messages:
        logger.warning("debounce_all_entries_invalid", phone=phone)
        return

    combined_body = "\n".join(m.get("body", "") for m in messages if m.get("body"))
    logger.info(
        "debounce_batch_processing",
        phone=phone,
        message_count=len(messages),
    )

    # Use first message as base, override body with combined
    # NOTE: For multimodal batches (Epic 3), only the LAST message's media_id
    # is preserved. If a user sends text + audio rapidly, the audio's media_id
    # takes priority. Text-only batches are unaffected.
    batch_data = messages[0].copy()
    batch_data["body"] = combined_body or batch_data.get("body", "")
    for m in messages[1:]:
        if m.get("media_id"):
            batch_data["media_id"] = m["media_id"]
            batch_data["mime_type"] = m.get("mime_type")
            batch_data["message_type"] = m.get("message_type", batch_data["message_type"])

    await process_callback(batch_data)
