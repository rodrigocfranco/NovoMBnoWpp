"""Graph node: load conversation context for the identified user."""

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from workflows.models import Message
from workflows.services.cache_manager import CacheManager
from workflows.utils.errors import GraphNodeError
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

CONTEXT_LIMIT = 20


async def load_context(state: WhatsAppState) -> dict:
    """Load conversation history for the identified user.

    1. Check Redis session cache for cached messages.
    2. On cache miss, query last 20 messages via Django ORM (async).
    3. Convert to LangChain messages (HumanMessage / AIMessage).
    4. Return in chronological order (oldest first).
    5. Cache the result in Redis (TTL 1h).

    Returns partial state dict with ``messages`` list.
    """
    user_id = state["user_id"]

    try:
        # Check cache first
        cached = await CacheManager.get_session(f"{user_id}:messages")
        if cached is not None:
            messages = _deserialize_messages(cached.get("messages", []))
            logger.info("context_loaded_from_cache", user_id=user_id, message_count=len(messages))
            return {"messages": messages}

        # Cache miss — query database
        queryset = Message.objects.filter(user_id=user_id).order_by("-created_at")[:CONTEXT_LIMIT]
        db_messages = [msg async for msg in queryset]

        # Reverse to chronological order (oldest first)
        db_messages.reverse()

        # Convert to LangChain messages
        lc_messages = _convert_to_langchain_messages(db_messages)

        # Cache the result
        serialized = _serialize_messages(lc_messages)
        await CacheManager.cache_session(
            f"{user_id}:messages",
            {"messages": serialized},
        )

        logger.info("context_loaded", user_id=user_id, message_count=len(lc_messages))
        return {"messages": lc_messages}

    except Exception as exc:
        logger.error(
            "node_error",
            node="load_context",
            user_id=user_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
            trace_id=state.get("trace_id", ""),
        )
        raise GraphNodeError(
            node="load_context",
            message=f"Failed to load context: {exc}",
        ) from exc


def _convert_to_langchain_messages(
    db_messages: list[Message],
) -> list[HumanMessage | AIMessage]:
    """Convert Django Message instances to LangChain message objects."""
    lc_messages: list[HumanMessage | AIMessage] = []
    for msg in db_messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
        else:
            logger.warning("message_role_skipped", role=msg.role, message_id=msg.id)
    return lc_messages


def _serialize_messages(messages: list[HumanMessage | AIMessage]) -> list[dict]:
    """Serialize LangChain messages for Redis cache storage."""
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"type": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"type": "ai", "content": msg.content})
    return result


def _deserialize_messages(data: list[dict]) -> list[HumanMessage | AIMessage]:
    """Deserialize cached message dicts back to LangChain messages."""
    messages: list[HumanMessage | AIMessage] = []
    for item in data:
        if item["type"] == "human":
            messages.append(HumanMessage(content=item["content"]))
        elif item["type"] == "ai":
            messages.append(AIMessage(content=item["content"]))
    return messages
