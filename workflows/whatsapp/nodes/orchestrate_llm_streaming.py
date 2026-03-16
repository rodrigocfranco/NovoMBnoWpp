"""Graph node: invoke LLM with streaming for better UX.

Streaming version of orchestrate_llm that processes LLM response chunks as they arrive,
enabling faster perceived response time and potential real-time WhatsApp updates.
"""

import asyncio

import structlog
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from workflows.providers.llm import get_model
from workflows.services.cost_tracker import CostTrackingCallback
from workflows.utils.errors import GraphNodeError
from workflows.whatsapp.prompts.system import build_system_message
from workflows.whatsapp.state import WhatsAppState
from workflows.whatsapp.tools import get_tools

logger = structlog.get_logger(__name__)

# LLM timeout: 15s max per invocation
LLM_TIMEOUT_SECONDS = 15.0


async def orchestrate_llm_streaming(state: WhatsAppState) -> dict:
    """Invoke LLM with streaming for better UX.

    Processes LLM response chunks as they arrive, enabling:
    1. Faster perceived response time (first chunk in ~500ms vs 7s for full response)
    2. Potential real-time WhatsApp updates (future: send partial messages)
    3. Early detection of tool calls (can start tool execution before full response)

    Returns partial state dict with ``messages`` (appended) and ``cost_usd``.
    """
    user_id = state["user_id"]
    user_message = state["user_message"]

    # Detect re-entry from tools loop
    current_messages = state["messages"]
    is_tool_reentry = bool(current_messages) and isinstance(current_messages[-1], ToolMessage)

    # Optimization: Use smaller max_tokens for tool calls
    max_tokens = 128 if is_tool_reentry else 1024

    model = get_model(tools=get_tools(), parallel_tool_calls=False, max_tokens=max_tokens)
    cost_tracker = CostTrackingCallback(user_id=user_id)

    # Build HumanMessage
    image_message = state.get("image_message")
    if image_message:
        user_msg = HumanMessage(content=image_message)
    else:
        user_msg = HumanMessage(content=user_message)

    if is_tool_reentry:
        messages = [build_system_message(), *current_messages]
    else:
        messages = [build_system_message(), *current_messages, user_msg]

    # Stream response
    accumulated_content = ""
    accumulated_tool_calls = []
    first_chunk_received = False
    first_chunk_latency_ms = None

    try:
        start_time = asyncio.get_event_loop().time()

        async def stream_with_timeout():
            """Stream LLM response with timeout."""
            async for chunk in model.astream(
                messages,
                config={"callbacks": [cost_tracker]},
            ):
                yield chunk

        async for chunk in asyncio.wait_for(
            stream_with_timeout(),
            timeout=LLM_TIMEOUT_SECONDS,
        ):
            # Track first chunk latency (perceived response time)
            if not first_chunk_received:
                first_chunk_received = True
                first_chunk_latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                logger.info(
                    "llm_first_chunk_received",
                    user_id=user_id,
                    latency_ms=round(first_chunk_latency_ms, 1),
                    is_tool_reentry=is_tool_reentry,
                )

            # Accumulate content
            if hasattr(chunk, "content") and chunk.content:
                accumulated_content += chunk.content

            # Accumulate tool calls
            if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                accumulated_tool_calls.extend(chunk.tool_calls)

            # Future: Send partial updates to WhatsApp here
            # if len(accumulated_content) > 50 and not accumulated_tool_calls:
            #     await send_partial_message(user_id, accumulated_content)

    except TimeoutError:
        logger.error(
            "llm_streaming_timeout_exceeded",
            node="orchestrate_llm_streaming",
            user_id=user_id,
            timeout_seconds=LLM_TIMEOUT_SECONDS,
            is_tool_reentry=is_tool_reentry,
            partial_content_length=len(accumulated_content),
        )
        raise GraphNodeError(
            node="orchestrate_llm_streaming",
            message=f"LLM streaming timeout after {LLM_TIMEOUT_SECONDS}s",
        )
    except Exception as exc:
        logger.error(
            "node_error",
            node="orchestrate_llm_streaming",
            user_id=user_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
            trace_id=state.get("trace_id", ""),
        )
        raise GraphNodeError(
            node="orchestrate_llm_streaming",
            message=f"Failed to stream LLM response: {exc}",
        ) from exc

    # Reconstruct AIMessage from accumulated chunks
    response = AIMessage(
        content=accumulated_content,
        tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
    )

    cost_summary = cost_tracker.get_cost_summary()

    # Detect provider (same logic as original)
    model_name = getattr(response, "response_metadata", {}).get("model_name", "")
    if "@" in model_name:
        provider_used = "vertex_ai"
    elif model_name:
        provider_used = "anthropic_direct"
    else:
        provider_used = "unknown"

    logger.info(
        "llm_streaming_completed",
        user_id=user_id,
        input_tokens=cost_summary["input_tokens"],
        output_tokens=cost_summary["output_tokens"],
        cost_usd=cost_summary["cost_usd"],
        provider_used=provider_used,
        is_tool_reentry=is_tool_reentry,
        max_tokens_used=max_tokens,
        first_chunk_latency_ms=round(first_chunk_latency_ms, 1) if first_chunk_latency_ms else None,
        total_content_length=len(accumulated_content),
        tool_calls_count=len(accumulated_tool_calls),
    )

    accumulated_cost = state.get("cost_usd", 0.0) + cost_summary["cost_usd"]
    return_messages = [response] if is_tool_reentry else [user_msg, response]

    return {
        "messages": return_messages,
        "cost_usd": accumulated_cost,
        "provider_used": provider_used,
    }
