"""Tests for CostTrackingCallback (AC1: model-aware pricing)."""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from workflows.services.cost_tracker import (
    MODEL_PRICING,
    CostTrackingCallback,
    _resolve_pricing,
)


def _make_llm_result(usage_metadata: dict | None = None) -> LLMResult:
    """Create an LLMResult with usage_metadata on the AIMessage."""
    msg = AIMessage(content="test response")
    if usage_metadata is not None:
        msg.usage_metadata = usage_metadata
    else:
        msg.usage_metadata = None
    gen = ChatGeneration(message=msg)
    return LLMResult(generations=[[gen]])


class TestResolvePricing:
    """Tests for _resolve_pricing function."""

    def test_haiku_vertex_model(self):
        pricing = _resolve_pricing("claude-haiku-4-5@20251001")
        assert pricing == MODEL_PRICING["haiku"]

    def test_haiku_direct_model(self):
        pricing = _resolve_pricing("claude-haiku-4-5-20251001")
        assert pricing == MODEL_PRICING["haiku"]

    def test_sonnet_vertex_model(self):
        pricing = _resolve_pricing("claude-sonnet-4@20250514")
        assert pricing == MODEL_PRICING["sonnet"]

    def test_sonnet_direct_model(self):
        pricing = _resolve_pricing("claude-sonnet-4-20250514")
        assert pricing == MODEL_PRICING["sonnet"]

    def test_unknown_model_defaults_to_haiku(self):
        pricing = _resolve_pricing("unknown-model")
        assert pricing == MODEL_PRICING["haiku"]

    def test_empty_model_defaults_to_haiku(self):
        pricing = _resolve_pricing("")
        assert pricing == MODEL_PRICING["haiku"]


class TestCostTrackingCallback:
    """Tests for CostTrackingCallback."""

    async def test_on_llm_end_extracts_usage_metadata(self):
        """AC1: on_llm_end extrai usage_metadata corretamente."""
        tracker = CostTrackingCallback(user_id="user-1")

        result = _make_llm_result(
            {
                "input_tokens": 1500,
                "output_tokens": 350,
                "input_token_details": {
                    "cache_read": 1000,
                    "cache_creation": 200,
                },
            }
        )

        with patch("workflows.services.cost_tracker.logger"):
            await tracker.on_llm_end(result)

        assert tracker.total_input == 1500
        assert tracker.total_output == 350
        assert tracker.cache_read == 1000
        assert tracker.cache_creation == 200

    async def test_cost_calculation_haiku_pricing(self):
        """AC1: Cálculo de custo com Haiku 4.5 pricing (default)."""
        tracker = CostTrackingCallback(user_id="user-1", model_name="claude-haiku-4-5@20251001")
        tracker.total_input = 1500
        tracker.total_output = 350
        tracker.cache_read = 1000
        tracker.cache_creation = 200

        summary = tracker.get_cost_summary()

        # Haiku 4.5 pricing: input $1.00, cache_read $0.10, cache_creation $1.25, output $5.00
        # base_input = 1500 - 1000 - 200 = 300
        # cost = 300 * 1.00/1M + 1000 * 0.10/1M + 200 * 1.25/1M + 350 * 5.00/1M
        # cost = 0.0003 + 0.0001 + 0.00025 + 0.00175 = 0.0024
        assert summary["cost_usd"] == pytest.approx(0.0024, abs=0.000001)
        assert summary["input_tokens"] == 1500
        assert summary["output_tokens"] == 350
        assert summary["cache_read_tokens"] == 1000
        assert summary["cache_creation_tokens"] == 200

    async def test_cost_calculation_sonnet_pricing(self):
        """AC1: Cálculo de custo com Sonnet 4 pricing (fallback)."""
        tracker = CostTrackingCallback(user_id="user-1", model_name="claude-sonnet-4@20250514")
        tracker.total_input = 1500
        tracker.total_output = 350
        tracker.cache_read = 1000
        tracker.cache_creation = 200

        summary = tracker.get_cost_summary()

        # Sonnet 4 pricing: input $3.00, cache_read $0.30, cache_creation $3.75, output $15.00
        # base_input = 1500 - 1000 - 200 = 300
        # cost = 300 * 3.00/1M + 1000 * 0.30/1M + 200 * 3.75/1M + 350 * 15.00/1M
        # cost = 0.0009 + 0.0003 + 0.00075 + 0.00525 = 0.0072
        assert summary["cost_usd"] == pytest.approx(0.0072, abs=0.000001)

    async def test_default_pricing_is_haiku(self):
        """AC1: Default pricing (sem model_name) usa Haiku 4.5."""
        tracker = CostTrackingCallback(user_id="user-1")
        tracker.total_input = 1000
        tracker.total_output = 100

        summary = tracker.get_cost_summary()

        # Haiku: 1000 * 1.00/1M + 100 * 5.00/1M = 0.001 + 0.0005 = 0.0015
        assert summary["cost_usd"] == pytest.approx(0.0015, abs=0.000001)

    async def test_cache_read_and_creation_differentiated(self):
        """AC1: cache_read e cache_creation são diferenciados."""
        tracker = CostTrackingCallback(user_id="user-1", model_name="claude-haiku-4-5@20251001")

        result = _make_llm_result(
            {
                "input_tokens": 2000,
                "output_tokens": 100,
                "input_token_details": {
                    "cache_read": 1500,
                    "cache_creation": 0,
                },
            }
        )

        with patch("workflows.services.cost_tracker.logger"):
            await tracker.on_llm_end(result)

        assert tracker.cache_read == 1500
        assert tracker.cache_creation == 0

        summary = tracker.get_cost_summary()
        # Haiku: base_input = 2000 - 1500 - 0 = 500
        # cost = 500 * 1.00/1M + 1500 * 0.10/1M + 0 + 100 * 5.00/1M
        # cost = 0.0005 + 0.00015 + 0.0005 = 0.00115
        assert summary["cost_usd"] == pytest.approx(0.00115, abs=0.000001)

    async def test_logs_cost_via_structlog(self):
        """AC1: Loga custo via structlog."""
        tracker = CostTrackingCallback(user_id="user-1")

        result = _make_llm_result(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "input_token_details": {},
            }
        )

        with patch("workflows.services.cost_tracker.logger") as mock_logger:
            await tracker.on_llm_end(result)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "cost_tracked"
            assert call_args[1]["user_id"] == "user-1"
            assert "cost_usd" in call_args[1]
            assert "input_tokens" in call_args[1]

    async def test_accumulates_across_multiple_calls(self):
        """AC1: Acumula tokens de múltiplas chamadas."""
        tracker = CostTrackingCallback(user_id="user-1")

        result1 = _make_llm_result(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "input_token_details": {},
            }
        )
        result2 = _make_llm_result(
            {
                "input_tokens": 200,
                "output_tokens": 75,
                "input_token_details": {"cache_read": 100},
            }
        )

        with patch("workflows.services.cost_tracker.logger"):
            await tracker.on_llm_end(result1)
            await tracker.on_llm_end(result2)

        assert tracker.total_input == 300
        assert tracker.total_output == 125
        assert tracker.cache_read == 100

    async def test_handles_missing_usage_metadata(self):
        """AC1: Trata gracefully quando usage_metadata é None."""
        tracker = CostTrackingCallback(user_id="user-1")

        result = _make_llm_result(None)

        with patch("workflows.services.cost_tracker.logger"):
            await tracker.on_llm_end(result)

        assert tracker.total_input == 0
        assert tracker.total_output == 0

    async def test_model_name_stored(self):
        """AC1: model_name é armazenado no tracker."""
        tracker = CostTrackingCallback(user_id="user-1", model_name="claude-haiku-4-5@20251001")
        assert tracker.model_name == "claude-haiku-4-5@20251001"
