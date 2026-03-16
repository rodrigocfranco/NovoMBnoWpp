"""Graph node: collect sources from tool execution results."""

import re

import structlog
from langchain_core.messages import HumanMessage, ToolMessage

from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

_WEB_SOURCE_PATTERN = re.compile(
    r"\[W-(\d+)\]\s+(.+?)\nURL:\s*(\S+)",
    re.MULTILINE,
)

_RAG_SOURCE_PATTERN = re.compile(
    r"^\[(\d+)\]\s+(.+)",
    re.MULTILINE,
)


async def collect_sources(state: WhatsAppState) -> dict:
    """Extract RAG and web sources from tool messages and populate state fields.

    Only processes messages from the current turn (after the last HumanMessage)
    to avoid accumulating stale sources from previous turns in multi-turn
    conversations with checkpointer.
    """
    web_sources: list[dict] = []
    retrieved_sources: list[dict] = []

    # Only process current turn: find last HumanMessage index
    messages = state["messages"]
    last_human_idx = -1
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            last_human_idx = i

    current_turn = messages[last_human_idx + 1 :] if last_human_idx >= 0 else messages

    for msg in current_turn:
        if not isinstance(msg, ToolMessage):
            continue
        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        if msg.name == "rag_medical_search":
            for match in _RAG_SOURCE_PATTERN.finditer(content):
                index = int(match.group(1))
                title = match.group(2).strip()
                retrieved_sources.append(
                    {
                        "index": index,
                        "title": title,
                        "type": "rag",
                    }
                )

        elif msg.name == "web_search":
            for match in _WEB_SOURCE_PATTERN.finditer(content):
                index = int(match.group(1))
                title = match.group(2).strip()
                url = match.group(3).strip()
                web_sources.append(
                    {
                        "index": index,
                        "title": title,
                        "url": url,
                        "type": "web",
                    }
                )

    if retrieved_sources:
        logger.info("rag_sources_collected", count=len(retrieved_sources))
    if web_sources:
        logger.info("web_sources_collected", count=len(web_sources))

    return {
        "retrieved_sources": retrieved_sources,
        "web_sources": web_sources,
    }
