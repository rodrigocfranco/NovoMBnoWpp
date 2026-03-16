"""Graph node: identify user by phone number."""

import structlog

from workflows.models import User
from workflows.services.cache_manager import CacheManager
from workflows.utils.errors import GraphNodeError
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)


async def identify_user(state: WhatsAppState) -> dict:
    """Identify or create a user from the phone number in state.

    1. Check Redis session cache first.
    2. On cache miss, query Django ORM (async).
    3. If user doesn't exist, create with subscription_tier='free'.
    4. Cache the result in Redis (TTL 1h).

    Returns partial state dict with ``user_id``, ``subscription_tier``, and ``is_new_user``.
    """
    phone = state["phone_number"]

    try:
        # Check cache first — cached users are never new
        cached = await CacheManager.get_session(phone)
        if cached is not None:
            logger.info("user_identified_from_cache", phone_suffix=phone[-4:])
            return {
                "user_id": cached["user_id"],
                "subscription_tier": cached["subscription_tier"],
                "is_new_user": False,
            }

        # Cache miss — query database
        is_new_user = False
        try:
            user = await User.objects.aget(phone=phone)
            logger.info("user_identified", phone_suffix=phone[-4:], user_id=str(user.id))
        except User.DoesNotExist:
            user = await User.objects.acreate(phone=phone, subscription_tier="free")
            is_new_user = True
            logger.info(
                "user_created",
                phone_suffix=phone[-4:],
                user_id=str(user.id),
                is_new_user=True,
            )

        session_data = {
            "user_id": str(user.id),
            "subscription_tier": user.subscription_tier,
        }

        # Cache the result keyed by phone (the lookup key)
        await CacheManager.cache_session(phone, session_data)

        return {**session_data, "is_new_user": is_new_user}

    except Exception as exc:
        logger.error(
            "node_error",
            node="identify_user",
            phone_suffix=phone[-4:],
            error_type=type(exc).__name__,
            error_message=str(exc),
            trace_id=state.get("trace_id", ""),
        )
        raise GraphNodeError(
            node="identify_user",
            message=f"Failed to identify user: {exc}",
        ) from exc
