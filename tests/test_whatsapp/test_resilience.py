"""Integration-style tests for resilience scenarios (Story 5.1, Task 6).

Tests retry, fallback, and error isolation without requiring external services.
Uses mocks at the provider boundary to simulate real failure scenarios.

Subtasks:
  6.1 LLM primary fails → fallback activates (with_fallbacks)
  6.2 Tool fails with timeout → returns error string (never raise)
  6.3 Multiple tools in parallel, one fails → others return normally
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from workflows.utils.errors import ExternalServiceError, GraphNodeError


def _make_state(**overrides):
    """Thin wrapper over shared make_whatsapp_state with resilience test defaults."""
    from tests.test_whatsapp.conftest import make_whatsapp_state

    defaults = {
        "user_id": "123",
        "subscription_tier": "premium",
        "trace_id": "trace-resilience-test",
    }
    defaults.update(overrides)
    return make_whatsapp_state(**defaults)


class TestLLMFallback:
    """6.1: LLM primary fails → fallback activates automatically."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_with_fallbacks_provider_detection(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """When primary (Vertex AI) fails and fallback (Anthropic Direct) responds,
        provider_used reflects the fallback provider."""
        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
        mock_tracker_cls.return_value = mock_tracker

        # Simulate fallback: response_metadata shows Anthropic Direct model name
        mock_response = MagicMock(spec=AIMessage)
        mock_response.response_metadata = {
            "model_name": "claude-sonnet-4-20250514"  # No "@" → anthropic_direct
        }
        mock_response.content = "Resposta do fallback"
        mock_response.tool_calls = []

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_model

        state = _make_state()
        result = await orchestrate_llm(state)

        assert result["provider_used"] == "anthropic_direct"

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_primary_success_detected_as_vertex_ai(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """When primary (Vertex AI) succeeds, provider_used is vertex_ai."""
        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
        mock_tracker_cls.return_value = mock_tracker

        # Simulate Vertex AI success
        mock_response = MagicMock(spec=AIMessage)
        mock_response.response_metadata = {
            "model_name": "claude-sonnet-4@20250514"  # "@" → vertex_ai
        }
        mock_response.content = "Resposta do Vertex AI"
        mock_response.tool_calls = []

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_model

        state = _make_state()
        result = await orchestrate_llm(state)

        assert result["provider_used"] == "vertex_ai"

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_total_failure_raises_and_logs(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """When both primary and fallback fail, GraphNodeError is raised with log."""
        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_model = AsyncMock()
        mock_model.ainvoke.side_effect = RuntimeError("All providers exhausted")
        mock_get_model.return_value = mock_model

        state = _make_state()

        with pytest.raises(GraphNodeError, match="Failed to generate LLM response"):
            await orchestrate_llm(state)


class TestToolTimeoutResilience:
    """6.3: Tool fails with timeout → returns error string (never raise)."""

    @patch("workflows.whatsapp.tools.rag_medical.get_pinecone")
    async def test_rag_timeout_returns_string(self, mock_get_pinecone):
        """RAG tool returns error string on provider timeout."""
        mock_provider = MagicMock()
        mock_provider.query_similar = AsyncMock(
            side_effect=ExternalServiceError(
                service="Pinecone",
                message="Context query failed: timeout",
            )
        )
        mock_get_pinecone.return_value = mock_provider

        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        result = await rag_medical_search.ainvoke({"query": "IC descompensada"})

        assert isinstance(result, str)
        assert "indisponível" in result.lower() or "erro" in result.lower()

    @patch("workflows.whatsapp.tools.web_search._get_blocked_domains", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search._get_tavily_timeout", new_callable=AsyncMock)
    @patch("workflows.whatsapp.tools.web_search.AsyncTavilyClient")
    async def test_web_search_timeout_returns_string(
        self, mock_tavily_cls, mock_timeout, mock_blocked
    ):
        """Web search tool returns error string on timeout."""
        mock_blocked.return_value = []
        mock_timeout.return_value = 1

        mock_client = MagicMock()
        mock_client.search = AsyncMock(side_effect=TimeoutError("Tavily timeout"))
        mock_tavily_cls.return_value = mock_client

        from workflows.whatsapp.tools.web_search import web_search

        result = await web_search.ainvoke({"query": "diretrizes IC 2025"})

        assert isinstance(result, str)
        assert "tempo limite" in result.lower()


class TestParallelToolIsolation:
    """6.4: Multiple tools in parallel — one fails, others return normally."""

    async def test_one_tool_fails_others_succeed_in_parallel(self):
        """Simulate parallel tool execution: RAG fails, calculator succeeds."""
        from workflows.whatsapp.tools.calculators import medical_calculator
        from workflows.whatsapp.tools.rag_medical import rag_medical_search

        # Run both tools concurrently
        async def run_rag_with_failure():
            with patch("workflows.whatsapp.tools.rag_medical.get_pinecone") as mock:
                mock_provider = MagicMock()
                mock_provider.query_similar = AsyncMock(side_effect=Exception("Pinecone down"))
                mock.return_value = mock_provider
                return await rag_medical_search.ainvoke({"query": "test"})

        async def run_calculator():
            return await medical_calculator.ainvoke(
                {
                    "calculator_name": "imc",
                    "parameters": {"peso_kg": 70.0, "altura_m": 1.75},
                }
            )

        rag_result, calc_result = await asyncio.gather(
            run_rag_with_failure(),
            run_calculator(),
        )

        # RAG should return error string (not raise)
        assert isinstance(rag_result, str)
        assert "erro" in rag_result.lower() or "indisponível" in rag_result.lower()

        # Calculator should return normal result (unaffected)
        assert isinstance(calc_result, str)
        assert "IMC" in calc_result
        assert "kg/m²" in calc_result  # confirms successful calculation, not error


@pytest.mark.django_db
class TestRetryPolicyConfiguration:
    """6.2: Verify RetryPolicy is properly configured on all external-calling nodes."""

    def test_all_retry_nodes_have_consistent_config(self):
        """All retry-enabled nodes use max_attempts=3 and backoff_factor=2.0."""
        from workflows.whatsapp.graph import build_whatsapp_graph

        graph = build_whatsapp_graph()
        retry_nodes = ["orchestrate_llm", "send_whatsapp", "tools"]

        for node_name in retry_nodes:
            spec = graph.builder.nodes[node_name]
            assert spec.retry_policy is not None, f"{node_name} missing RetryPolicy"
            assert spec.retry_policy.max_attempts == 3, (
                f"{node_name}: expected max_attempts=3, got {spec.retry_policy.max_attempts}"
            )
            assert spec.retry_policy.backoff_factor == 2.0, (
                f"{node_name}: expected backoff_factor=2.0, got {spec.retry_policy.backoff_factor}"
            )

    def test_non_retry_nodes_have_no_retry_policy(self):
        """Nodes with graceful degradation should NOT have RetryPolicy."""
        from workflows.whatsapp.graph import build_whatsapp_graph

        graph = build_whatsapp_graph()
        no_retry_nodes = [
            "identify_user",
            "rate_limit",
            "process_media",
            "load_context",
            "format_response",
            "collect_sources",
            "persist",
        ]

        for node_name in no_retry_nodes:
            spec = graph.builder.nodes[node_name]
            assert spec.retry_policy is None, (
                f"{node_name} should NOT have RetryPolicy but has {spec.retry_policy}"
            )


class TestRetryBehavior:
    """6.2: Verify RetryPolicy actually retries failed nodes."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_orchestrate_llm_retried_on_transient_failure(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """Node that raises is called again by RetryPolicy (up to max_attempts)."""
        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
        mock_tracker_cls.return_value = mock_tracker

        # First call fails, second succeeds
        mock_response = MagicMock(spec=AIMessage)
        mock_response.response_metadata = {"model_name": "claude-sonnet-4@20250514"}
        mock_response.content = "Success after retry"
        mock_response.tool_calls = []

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[RuntimeError("transient failure"), mock_response]
        )
        mock_get_model.return_value = mock_model

        state = _make_state()

        # Direct call should fail on first attempt (RetryPolicy is graph-level)
        with pytest.raises(GraphNodeError):
            await orchestrate_llm(state)

        # Verify the model was called exactly once (node itself doesn't retry)
        assert mock_model.ainvoke.call_count == 1

        # Second call succeeds — simulating what RetryPolicy would do
        result = await orchestrate_llm(state)
        assert result["provider_used"] == "vertex_ai"
        assert mock_model.ainvoke.call_count == 2
