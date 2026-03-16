"""Langfuse provider for LangChain/LangGraph tracing (Story 7.2)."""

import structlog
from django.conf import settings
from langfuse import get_client
from langfuse.langchain import CallbackHandler

logger = structlog.get_logger(__name__)


def is_langfuse_enabled() -> bool:
    """Check if Langfuse tracing is enabled via settings."""
    return getattr(settings, "LANGFUSE_ENABLED", False)


def get_langfuse_handler(
    trace_id: str,
) -> CallbackHandler | None:
    """Create Langfuse CallbackHandler for LangGraph tracing.

    Returns None when LANGFUSE_ENABLED is False, allowing callers to skip
    adding the callback without conditional logic everywhere.

    The trace_id, user_id, session_id, tags, and metadata are propagated
    via ``langfuse.propagate_attributes()`` context manager at the call site
    (views.py), not passed directly to the handler constructor.

    Args:
        trace_id: Correlation ID from TraceIDMiddleware (structlog contextvars).

    Returns:
        CallbackHandler instance or None if disabled.
    """
    if not is_langfuse_enabled():
        return None

    handler = CallbackHandler()
    logger.debug("langfuse_handler_created", trace_id=trace_id)
    return handler


def update_trace_metadata(
    trace_id: str,
    user_id: str = "",
    metadata: dict | None = None,
) -> None:
    """Update Langfuse trace with post-execution metadata (AC4).

    Called after graph.ainvoke() completes, when user_id and business
    metadata (subscription_tier, provider_used) are available from the
    graph result. Uses trace upsert — updates existing trace created
    by CallbackHandler during execution.

    No-op when Langfuse is disabled.
    """
    if not is_langfuse_enabled():
        return

    try:
        client = get_client()
        client.trace(id=trace_id, user_id=user_id, metadata=metadata or {})
        logger.debug("langfuse_trace_updated", trace_id=trace_id, user_id=user_id)
    except Exception:
        logger.exception("langfuse_trace_update_error", trace_id=trace_id)


def shutdown_langfuse() -> None:
    """Flush pending traces and shutdown Langfuse client.

    Called via atexit handler registered in WorkflowsConfig.ready().
    No-op when Langfuse is disabled.
    """
    if not is_langfuse_enabled():
        return

    try:
        client = get_client()
        client.shutdown()
        logger.info("langfuse_shutdown_complete")
    except Exception:
        logger.exception("langfuse_shutdown_error")
