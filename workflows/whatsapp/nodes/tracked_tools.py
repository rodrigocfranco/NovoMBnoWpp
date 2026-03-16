"""Wrapper around ToolNode that tracks execution metadata (Story 7.1)."""

import time

import structlog
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode

from workflows.whatsapp.state import WhatsAppState
from workflows.whatsapp.tools import get_tools

logger = structlog.get_logger(__name__)

_tool_node = ToolNode(get_tools(), handle_tool_errors=True)


async def tracked_tools(state: WhatsAppState) -> dict:
    """Execute tools via ToolNode and track execution metadata."""
    start = time.monotonic()
    result = await _tool_node.ainvoke(state)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    tool_messages = [m for m in result.get("messages", []) if isinstance(m, ToolMessage)]
    prev_executions = state.get("tool_executions") or []
    new_executions = []
    for msg in tool_messages:
        is_error = hasattr(msg, "status") and msg.status == "error"
        # parallel_tool_calls=False (ADR-013) → one tool per invocation,
        # so elapsed_ms applies to each message directly
        new_executions.append(
            {
                "tool_name": msg.name or "unknown",
                "latency_ms": elapsed_ms,
                "success": not is_error,
                "error": msg.content[:500] if is_error else None,
            }
        )

    logger.info(
        "tools_executed",
        tool_count=len(new_executions),
        total_latency_ms=elapsed_ms,
        user_id=state.get("user_id"),
    )

    return {
        **result,
        "tool_executions": prev_executions + new_executions,
    }
