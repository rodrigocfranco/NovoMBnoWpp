"""LLM provider factory with Vertex AI primary and Anthropic Direct fallback."""

import json
from typing import Any

import structlog
from django.conf import settings
from langchain_anthropic import ChatAnthropic
from langchain_google_vertexai.model_garden import ChatAnthropicVertex

logger = structlog.get_logger(__name__)

_default_model: Any = None
_tools_model: Any = None


def get_model(
    *,
    temperature: float = 0,
    max_tokens: int = 1024,
    tools: list | None = None,
    parallel_tool_calls: bool = True,
) -> Any:
    """Return LLM with Vertex AI primary and Anthropic Direct fallback.

    Returns a cached singleton for default parameters. Non-default parameters
    bypass the cache and create a fresh instance.

    When ``tools`` are provided, they are bound to BOTH primary and fallback
    models before ``with_fallbacks()``, preserving the fallback chain.

    Args:
        temperature: Sampling temperature (default 0 for deterministic).
        max_tokens: Maximum output tokens (default 1024). Reduced from 2048 as medical
            responses typically range 300-800 tokens, providing faster response and lower cost.
        tools: Optional list of LangChain tools to bind.
        parallel_tool_calls: Allow LLM to call multiple tools in parallel (default True).
            Set to False to force sequential tool calling, preventing redundant calls.
    """
    global _default_model, _tools_model

    is_default = temperature == 0 and max_tokens == 1024 and parallel_tool_calls

    if is_default:
        cached = _tools_model if tools else _default_model
        if cached is not None:
            return cached

    model = _build_model(
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        parallel_tool_calls=parallel_tool_calls,
    )

    if is_default:
        if tools:
            _tools_model = model
        else:
            _default_model = model

    return model


def _build_model(
    *,
    temperature: float,
    max_tokens: int,
    tools: list | None = None,
    parallel_tool_calls: bool = True,
) -> Any:
    """Build a new RunnableWithFallbacks instance.

    Uses Claude Haiku 4.5 for tool calling orchestration (fast, cheap, excellent routing).
    Haiku is optimal for tool selection vs Sonnet 4 which over-thinks and is 15x more expensive.

    Args:
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        tools: Optional list of LangChain tools to bind.
        parallel_tool_calls: Allow LLM to call multiple tools in parallel.
    """
    vertex_kwargs: dict[str, Any] = {
        "model_name": "claude-haiku-4-5@20251001",
        "project": settings.VERTEX_PROJECT_ID,
        "location": settings.VERTEX_LOCATION,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "streaming": True,
        "max_retries": 2,
    }

    if settings.GCP_CREDENTIALS:
        from google.oauth2 import service_account

        creds_info = json.loads(settings.GCP_CREDENTIALS)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        vertex_kwargs["credentials"] = credentials

    primary = ChatAnthropicVertex(**vertex_kwargs)

    fallback = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=max_tokens,
        temperature=temperature,
        streaming=True,
        max_retries=2,
        stream_usage=True,
    )

    if tools:
        primary = primary.bind_tools(tools)
        fallback = fallback.bind_tools(tools)

        # Disable parallel tool use via tool_choice when parallel_tool_calls=False
        # Anthropic API uses tool_choice.disable_parallel_tool_use to enforce sequential calling
        if not parallel_tool_calls:
            tool_choice = {"type": "auto", "disable_parallel_tool_use": True}
            primary = primary.bind(tool_choice=tool_choice)
            fallback = fallback.bind(tool_choice=tool_choice)

    logger.debug(
        "llm_provider_initialized",
        primary="ChatAnthropicVertex",
        fallback="ChatAnthropic",
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return primary.with_fallbacks([fallback])
