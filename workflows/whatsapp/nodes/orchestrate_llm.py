"""Graph node: invoke LLM with system prompt, history, and cost tracking."""

import asyncio

import structlog
from langchain_core.messages import HumanMessage, ToolMessage

from workflows.providers.llm import get_model
from workflows.services.cost_tracker import CostTrackingCallback
from workflows.utils.errors import GraphNodeError
from workflows.whatsapp.prompts.system import build_system_message
from workflows.whatsapp.state import WhatsAppState
from workflows.whatsapp.tools import get_tools

logger = structlog.get_logger(__name__)

# LLM timeout: 15s max per invocation (safety against edge cases)
LLM_TIMEOUT_SECONDS = 15.0


async def orchestrate_llm(state: WhatsAppState) -> dict:
    """Invoke LLM with system prompt + conversation history + user message.

    1. Build message list: system prompt (with cache_control) + history + user message.
    2. Create CostTrackingCallback to track token usage.
    3. Invoke model via ainvoke with callbacks.
    4. Return partial state with response message and cost.

    Returns partial state dict with ``messages`` (appended) and ``cost_usd``.
    """
    user_id = state["user_id"]
    user_message = state["user_message"]

    # Detect re-entry from tools loop (last message is a ToolMessage)
    current_messages = state["messages"]
    is_tool_reentry = bool(current_messages) and isinstance(current_messages[-1], ToolMessage)

    # Optimization: smaller max_tokens for tool calls (selection only)
    # Tool calls: 128 tokens (just tool name + args)
    # Final response: 1024 tokens (full medical answer)
    max_tokens = 128 if is_tool_reentry else 1024

    # State access and setup outside try — programming bugs should NOT be retried
    # parallel_tool_calls=False forces sequential tool calling, preventing redundant calls
    # (e.g., calling drug_lookup + RAG + web_search simultaneously for a single query)
    model = get_model(tools=get_tools(), parallel_tool_calls=False, max_tokens=max_tokens)
    cost_tracker = CostTrackingCallback(user_id=user_id, model_name="")

    # Build HumanMessage: multimodal (image) or plain text
    image_message = state.get("image_message")
    if image_message:
        user_msg = HumanMessage(content=image_message)
    else:
        user_msg = HumanMessage(content=user_message)

    system_msg = await build_system_message()
    if is_tool_reentry:
        # Re-entry: state already has user message + AI tool_calls + tool results
        messages = [system_msg, *current_messages]
    else:
        # First entry: add user message to context
        messages = [system_msg, *current_messages, user_msg]

    try:
        # Add timeout to prevent edge cases from hanging (15s max)
        response = await asyncio.wait_for(
            model.ainvoke(
                messages,
                config={"callbacks": [cost_tracker]},
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.error(
            "llm_timeout_exceeded",
            node="orchestrate_llm",
            user_id=user_id,
            timeout_seconds=LLM_TIMEOUT_SECONDS,
            is_tool_reentry=is_tool_reentry,
            max_tokens=max_tokens,
            trace_id=state.get("trace_id", ""),
        )
        raise GraphNodeError(
            node="orchestrate_llm",
            message=f"LLM timeout after {LLM_TIMEOUT_SECONDS}s",
        )
    except Exception as exc:
        logger.error(
            "node_error",
            node="orchestrate_llm",
            user_id=user_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
            trace_id=state.get("trace_id", ""),
        )
        raise GraphNodeError(
            node="orchestrate_llm",
            message=f"Failed to generate LLM response: {exc}",
        ) from exc

    # Detect which provider responded via response_metadata.model_name
    # Vertex AI returns model names with "@" (e.g. "claude-sonnet-4@20250514")
    # Anthropic Direct returns model names with "-" (e.g. "claude-sonnet-4-20250514")
    # WARNING: This heuristic relies on undocumented naming conventions from
    # langchain-google-vertexai and langchain-anthropic. Pin library versions
    # and monitor for changes. Falls back to "unknown" on unexpected formats.
    response_metadata = getattr(response, "response_metadata", None) or {}
    model_name = response_metadata.get("model_name", "")
    if "@" in model_name:
        provider_used = "vertex_ai"
    elif model_name:
        provider_used = "anthropic_direct"
    else:
        provider_used = "unknown"

    # Set model_name BEFORE get_cost_summary() for accurate pricing
    # (Review Fix H1: was previously set after cost calculation)
    cost_tracker.model_name = model_name
    cost_summary = cost_tracker.get_cost_summary()

    # Extract cache metrics (Vertex AI specific)
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    cache_creation_tokens = usage_metadata.get("cache_creation_input_tokens", 0)
    cache_read_tokens = usage_metadata.get("cache_read_input_tokens", 0)

    logger.info(
        "llm_response_generated",
        user_id=user_id,
        input_tokens=cost_summary["input_tokens"],
        output_tokens=cost_summary["output_tokens"],
        cost_usd=cost_summary["cost_usd"],
        provider_used=provider_used,
        is_tool_reentry=is_tool_reentry,
        max_tokens_used=max_tokens,
        # Cache metrics (Vertex AI only, 0 if Anthropic Direct)
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_hit=cache_read_tokens > 0,
    )

    # Accumulate cost across tool-loop iterations (state.cost_usd carries previous calls)
    accumulated_cost = state.get("cost_usd", 0.0) + cost_summary["cost_usd"]

    return_messages = [response] if is_tool_reentry else [user_msg, response]

    return {
        "messages": return_messages,
        "cost_usd": accumulated_cost,
        "provider_used": provider_used,
        # Story 7.1: token breakdown for CostLog
        "tokens_input": state.get("tokens_input", 0) + cost_summary["input_tokens"],
        "tokens_output": state.get("tokens_output", 0) + cost_summary["output_tokens"],
        "tokens_cache_read": state.get("tokens_cache_read", 0) + cost_summary["cache_read_tokens"],
        "tokens_cache_creation": (
            state.get("tokens_cache_creation", 0) + cost_summary["cache_creation_tokens"]
        ),
        "model_used": model_name,
    }
