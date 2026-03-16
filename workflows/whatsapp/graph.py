"""WhatsApp conversation graph built with LangGraph."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import tools_condition
from langgraph.types import RetryPolicy

from workflows.whatsapp.nodes.collect_sources import collect_sources
from workflows.whatsapp.nodes.format_response import format_response
from workflows.whatsapp.nodes.identify_user import identify_user
from workflows.whatsapp.nodes.load_context import load_context
from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm
from workflows.whatsapp.nodes.persist import persist
from workflows.whatsapp.nodes.process_media import process_media
from workflows.whatsapp.nodes.rate_limit import check_rate_limit, rate_limit
from workflows.whatsapp.nodes.send_whatsapp import send_whatsapp
from workflows.whatsapp.nodes.tracked_tools import tracked_tools
from workflows.whatsapp.state import WhatsAppState

_compiled_graph: CompiledStateGraph | None = None


def build_whatsapp_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build and compile the WhatsApp conversation StateGraph.

    Flow: START → identify_user → rate_limit → [check_rate_limit]
          → process_media → load_context → orchestrate_llm → [tools_condition]
          → tools (loop) OR collect_sources → format_response
          → send_whatsapp → persist → END

    If rate_limit_exceeded: rate_limit → END (no LLM call).
    If LLM requests tools: orchestrate_llm → tools → orchestrate_llm (loop).

    Args:
        checkpointer: Optional checkpoint saver for conversation persistence.
            When provided, thread_id (phone_number) enables automatic history.
    """
    builder = StateGraph(WhatsAppState)

    # Add nodes
    # Story 5.1: RetryPolicy decisions per node:
    # - identify_user: NO — graceful fallback (cache→DB→create)
    # - rate_limit: NO — fail-open design
    # - process_media: NO — providers have own retry
    # - load_context: NO — graceful fallback (cache→DB→empty)
    # - orchestrate_llm: YES — transient LLM failures
    # - format_response: NO — local processing only
    # - send_whatsapp: YES — transient WA API failures
    # - persist: NO — catches DatabaseError internally
    # - tools: YES — external services can fail transiently
    # - collect_sources: NO — local processing only
    builder.add_node("identify_user", identify_user)
    builder.add_node("rate_limit", rate_limit)
    builder.add_node("process_media", process_media)
    builder.add_node("load_context", load_context)
    builder.add_node(
        "orchestrate_llm",
        orchestrate_llm,
        retry_policy=RetryPolicy(max_attempts=3, backoff_factor=2.0),
    )
    builder.add_node("format_response", format_response)
    builder.add_node(
        "send_whatsapp",
        send_whatsapp,
        retry_policy=RetryPolicy(max_attempts=3, backoff_factor=2.0),
    )
    builder.add_node("persist", persist)
    builder.add_node(
        "tools",
        tracked_tools,
        retry_policy=RetryPolicy(max_attempts=3, backoff_factor=2.0),
    )
    builder.add_node("collect_sources", collect_sources)

    # Add edges
    builder.add_edge(START, "identify_user")
    builder.add_edge("identify_user", "rate_limit")
    builder.add_conditional_edges("rate_limit", check_rate_limit)
    builder.add_edge("process_media", "load_context")
    builder.add_edge("load_context", "orchestrate_llm")
    builder.add_conditional_edges(
        "orchestrate_llm",
        tools_condition,
        {"tools": "tools", "__end__": "collect_sources"},
    )
    builder.add_edge("tools", "orchestrate_llm")
    builder.add_edge("collect_sources", "format_response")
    builder.add_edge("format_response", "send_whatsapp")
    builder.add_edge("send_whatsapp", "persist")
    builder.add_edge("persist", END)

    return builder.compile(checkpointer=checkpointer)


async def get_graph() -> CompiledStateGraph:
    """Return compiled graph singleton with checkpointer."""
    global _compiled_graph
    if _compiled_graph is None:
        from workflows.providers.checkpointer import get_checkpointer

        checkpointer = await get_checkpointer()
        _compiled_graph = build_whatsapp_graph(checkpointer=checkpointer)
    return _compiled_graph
