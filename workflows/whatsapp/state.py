"""WhatsApp conversation state for LangGraph StateGraph."""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class WhatsAppState(TypedDict):
    """State schema for the WhatsApp conversation graph.

    Nodes return partial dicts with only the fields they modify.
    The ``messages`` field uses ``add_messages`` reducer for automatic accumulation.
    """

    # Input fields (populated from webhook data)
    phone_number: str
    user_message: str
    message_type: str
    media_url: str | None
    media_id: str | None
    mime_type: str | None
    wamid: str

    # Identification fields (populated by identify_user node)
    user_id: str
    subscription_tier: str
    is_new_user: bool

    # Context field — LangGraph message accumulation via add_messages reducer
    messages: Annotated[list[AnyMessage], add_messages]

    # Output fields (Story 1.5)
    formatted_response: str
    additional_responses: list[str]
    response_sent: bool

    # Observability fields
    trace_id: str
    cost_usd: float

    # Citation fields (placeholder for Story 2.x)
    retrieved_sources: list[dict]
    cited_source_indices: list[int]
    web_sources: list[dict]

    # Rate limiting fields (Story 4.1)
    rate_limit_exceeded: bool
    remaining_daily: int
    rate_limit_warning: str

    # Audio transcription (Story 3.1)
    transcribed_text: str

    # Image Vision (Story 3.2) — multimodal content blocks for Claude Vision
    image_message: list | None

    # Resilience tracking (Story 5.1)
    provider_used: str  # "vertex_ai" or "anthropic_direct"

    # Cost tracking fields (Story 7.1)
    tokens_input: int
    tokens_output: int
    tokens_cache_read: int
    tokens_cache_creation: int
    model_used: str
    tool_executions: list[dict]
