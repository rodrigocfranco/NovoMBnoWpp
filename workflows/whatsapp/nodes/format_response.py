"""Graph node: format LLM response for WhatsApp delivery."""

import re

import structlog
from langchain_core.messages import AIMessage

from workflows.utils.formatters import (
    add_medical_disclaimer,
    detect_content_type,
    markdown_to_whatsapp,
    should_add_disclaimer,
)
from workflows.utils.message_splitter import split_message
from workflows.whatsapp.state import WhatsAppState

logger = structlog.get_logger(__name__)

COMPETITOR_NAMES = [
    "medcurso",
    "medgrupo",
    "medcof",
    "estratégia med",
    "estrategia med",
    "medcel",
    "afya",
    "sanar",
    "sanarflix",
    "aristo",
    "jj medicina",
    "eu médico residente",
    "eu medico residente",
    "revisamed",
    "mediccurso",
    "medprovas",
    "vr med",
    "vrmed",
    "medmentoria",
    "o residente",
    "oresidente",
    "yellowbook",
]

# Pre-compiled regex patterns for competitor blocking (M3: avoid per-call compilation)
_COMPETITOR_PATTERNS = [
    (name, re.compile(re.escape(name), re.IGNORECASE)) for name in COMPETITOR_NAMES
]


def validate_citations(text: str, available_sources: list[dict]) -> str:
    """Remove citation markers ``[N]`` that don't correspond to real sources.

    When ``available_sources`` is empty (no tools active), strips ALL
    ``[N]`` and ``[W-N]`` markers since they are LLM hallucinations.
    """
    if not available_sources:
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\[W-\d+\]", "", text)
        return text

    rag_indices = {s.get("index") for s in available_sources if s.get("type") == "rag"}
    web_indices = {s.get("index") for s in available_sources if s.get("type") == "web"}

    def check_rag(match: re.Match) -> str:
        n = int(match.group(1))
        return match.group(0) if n in rag_indices else ""

    def check_web(match: re.Match) -> str:
        n = int(match.group(1))
        return match.group(0) if n in web_indices else ""

    text = re.sub(r"\[(\d+)\]", check_rag, text)
    text = re.sub(r"\[W-(\d+)\]", check_web, text)
    return text


def strip_competitor_citations(text: str) -> str:
    """Remove mentions of competitor brands from the response."""
    for name, pattern in _COMPETITOR_PATTERNS:
        if pattern.search(text):
            logger.warning("competitor_citation_blocked", competitor=name)
            text = pattern.sub("[fonte removida]", text)
    return text


def _build_source_footer(rag_sources: list[dict], web_sources: list[dict]) -> str:
    """Build formatted source footer for WhatsApp."""
    lines: list[str] = []
    if rag_sources:
        lines.append("\U0001f4da *Fontes:*")
        for src in rag_sources:
            idx = src.get("index", "?")
            title = src.get("title", "Fonte desconhecida")
            lines.append(f"[{idx}] {title}")
    if web_sources:
        lines.append("\U0001f310 *Web:*")
        for src in web_sources:
            idx = src.get("index", "?")
            title = src.get("title", "")
            url = src.get("url", "")
            lines.append(f"[W-{idx}] {title} \u2014 {url}")
    return "\n".join(lines)


async def format_response(state: WhatsAppState) -> dict:
    """Format LLM response for WhatsApp delivery.

    Pipeline:
    1. Extract text from last AIMessage
    2. Detect content type (on original text, before transformations)
    3. Validate citations (strip hallucinated [N] markers)
    4. Strip competitor citations
    5. Convert Markdown -> WhatsApp formatting
    6. Append rate limit warning if present
    7. Add medical disclaimer if applicable
    8. Split if exceeds 4096 chars

    Returns partial state dict with ``formatted_response`` and ``additional_responses``.
    """
    # Extract content from last AIMessage
    messages = state["messages"]
    ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            # Handle list content (Vision API returns list of dicts)
            if isinstance(content, list):
                ai_content = " ".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            else:
                ai_content = content
            break

    # Detect content type on original text (L3: before transformations)
    content_type = detect_content_type(ai_content)

    # Citation validation
    available_sources = state.get("retrieved_sources", []) + state.get("web_sources", [])
    text = validate_citations(ai_content, available_sources)

    # Extract cited source indices from validated text
    cited_source_indices = [int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", text)]

    # Competitor blocking
    text = strip_competitor_citations(text)

    # Source footer (before markdown conversion so markers format correctly)
    source_footer = _build_source_footer(
        state.get("retrieved_sources", []),
        state.get("web_sources", []),
    )
    if source_footer:
        text = text + "\n\n" + source_footer

    # Markdown -> WhatsApp
    text = markdown_to_whatsapp(text)

    # Append rate limit warning BEFORE disclaimer (so it's not hidden below it)
    rate_limit_warning = state.get("rate_limit_warning", "")
    if rate_limit_warning:
        text = text + "\n\n" + rate_limit_warning

    # Medical disclaimer (always last, after warning)
    if should_add_disclaimer(text):
        text = add_medical_disclaimer(text)

    # Split if needed
    parts = split_message(text)
    formatted_response = parts[0]
    additional_responses = parts[1:] if len(parts) > 1 else []

    logger.info(
        "response_formatted",
        content_type=content_type,
        char_count=len(text),
        parts_count=len(parts),
    )

    return {
        "formatted_response": formatted_response,
        "additional_responses": additional_responses,
        "cited_source_indices": cited_source_indices,
    }
