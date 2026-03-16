"""Graph node: persist user message and assistant response via Django ORM."""

from decimal import Decimal

import structlog
from django.db import DatabaseError

from workflows.models import CostLog, Message, ToolExecution, User
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)


async def persist(state: WhatsAppState) -> dict:
    """Persist user message, assistant response, CostLog, and ToolExecution records.

    Creates:
    1. User message (role="user")
    2. Assistant response (role="assistant") with cost_usd
    3. CostLog record with token breakdown (Story 7.1)
    4. ToolExecution records for each tool call (Story 7.1)

    Database errors are silenced (user already received the response).
    Programming errors (AttributeError, TypeError, etc.) propagate to
    aid debugging.

    Returns empty dict (last node before END, no state changes needed).
    """
    try:
        # Review Fix M2: moved inside try — ValueError caught as best-effort
        user_id = int(state["user_id"])
        user = await User.objects.aget(id=user_id)

        # Persist user message
        await Message.objects.acreate(
            user=user,
            content=state["user_message"],
            role="user",
            message_type=state.get("message_type", "text"),
        )

        # Persist assistant response
        cost_usd = state.get("cost_usd")
        cost_decimal = Decimal(str(cost_usd)) if cost_usd else None

        await Message.objects.acreate(
            user=user,
            content=state["formatted_response"],
            role="assistant",
            message_type="text",
            cost_usd=cost_decimal,
        )

        # Create CostLog record (Story 7.1)
        # Review Fix M1: create for cost_usd >= 0 (was: > 0) for complete tracking
        if cost_usd is not None:
            await CostLog.objects.acreate(
                user=user,
                provider=state.get("provider_used", "unknown"),
                model=state.get("model_used", "unknown"),
                tokens_input=state.get("tokens_input", 0),
                tokens_output=state.get("tokens_output", 0),
                tokens_cache_creation=state.get("tokens_cache_creation", 0),
                tokens_cache_read=state.get("tokens_cache_read", 0),
                cost_usd=Decimal(str(cost_usd)),
            )

        # Create ToolExecution records (Story 7.1)
        tool_executions = state.get("tool_executions") or []
        for exec_data in tool_executions:
            await ToolExecution.objects.acreate(
                user=user,
                tool_name=exec_data["tool_name"],
                latency_ms=exec_data.get("latency_ms"),
                success=exec_data.get("success", True),
                error=exec_data.get("error"),
            )

        logger.info(
            "data_persisted",
            user_id=user_id,
            cost_usd=float(cost_decimal) if cost_decimal else 0.0,
            cost_log_created=cost_usd is not None,
            tool_executions_count=len(tool_executions),
        )

    except (DatabaseError, User.DoesNotExist, ValueError) as exc:
        # DB unavailable, user deleted, or invalid user_id — don't block pipeline
        logger.exception(
            "persist_failed",
            node="persist",
            user_id=state.get("user_id", "unknown"),
            error_type=type(exc).__name__,
        )

    return {}
