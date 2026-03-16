"""Integration test for LLM pipeline with REAL Vertex AI / Anthropic.

Validates the full LLM pipeline end-to-end:
- get_model() creates a working RunnableWithFallbacks
- Vertex AI (primary) or Anthropic (fallback) responds
- CostTrackingCallback captures token usage
- with_fallbacks() works correctly

Run:
    DJANGO_SETTINGS_MODULE=config.settings.integration \
    pytest tests/integration/test_llm_pipeline.py -m integration -s
"""

import pytest
from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage

from workflows.providers.llm import _build_model
from workflows.services.cost_tracker import CostTrackingCallback

pytestmark = pytest.mark.integration


def _has_llm_credentials() -> bool:
    """Check if LLM credentials are configured."""
    return bool(settings.GCP_CREDENTIALS or settings.ANTHROPIC_API_KEY)


@pytest.mark.skipif(
    not _has_llm_credentials(),
    reason="LLM credentials not configured (GCP_CREDENTIALS or ANTHROPIC_API_KEY)",
)
class TestLLMPipelineReal:
    """LLM pipeline with real API calls."""

    async def test_model_responds_to_simple_prompt(self):
        """Model responde a prompt simples via Vertex AI ou fallback."""
        model = _build_model(temperature=0, max_tokens=100)
        messages = [HumanMessage(content="Responda apenas 'ok'.")]

        response = await model.ainvoke(messages)

        assert isinstance(response, AIMessage)
        assert len(response.content) > 0
        assert "ok" in response.content.lower()

    async def test_cost_tracking_captures_usage(self):
        """CostTrackingCallback captura tokens e custo."""
        tracker = CostTrackingCallback(user_id="test-integration")
        model = _build_model(temperature=0, max_tokens=100)
        messages = [HumanMessage(content="Diga apenas 'teste'.")]

        response = await model.ainvoke(messages, config={"callbacks": [tracker]})

        assert isinstance(response, AIMessage)
        summary = tracker.get_cost_summary()
        assert summary["input_tokens"] > 0
        assert summary["output_tokens"] > 0
        assert summary["cost_usd"] > 0

    async def test_with_fallbacks_returns_response(self):
        """with_fallbacks() retorna resposta (primary ou fallback)."""
        model = _build_model(temperature=0, max_tokens=50)

        response = await model.ainvoke([HumanMessage(content="1+1=?")])

        assert isinstance(response, AIMessage)
        assert "2" in response.content
