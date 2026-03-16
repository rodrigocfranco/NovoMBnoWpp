"""Cost tracking callback for LLM usage via structlog."""

from typing import Any

import structlog
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = structlog.get_logger(__name__)

# Pricing per million tokens (USD) — Anthropic pricing (March 2026)
# Vertex AI uses same base pricing.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "haiku": {  # Claude Haiku 4.5
        "input": 1.00,
        "cache_read": 0.10,
        "cache_creation": 1.25,
        "output": 5.00,
    },
    "sonnet": {  # Claude Sonnet 4 (fallback / legacy)
        "input": 3.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
        "output": 15.00,
    },
}
DEFAULT_PRICING_KEY = "haiku"


def _resolve_pricing(model_name: str) -> dict[str, float]:
    """Select pricing tier based on model name substring match."""
    model_lower = model_name.lower()
    if "haiku" in model_lower:
        return MODEL_PRICING["haiku"]
    if "sonnet" in model_lower:
        return MODEL_PRICING["sonnet"]
    return MODEL_PRICING[DEFAULT_PRICING_KEY]


class CostTrackingCallback(AsyncCallbackHandler):
    """Track LLM cost per invocation via usage_metadata.

    Extracts token counts from AIMessage.usage_metadata and calculates
    cost using model-aware pricing. Logs via structlog (JSON).
    """

    def __init__(self, user_id: str, model_name: str = "") -> None:
        self.user_id = user_id
        self.model_name = model_name
        self.total_input: int = 0
        self.total_output: int = 0
        self.cache_read: int = 0
        self.cache_creation: int = 0

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Extract usage_metadata from LLM response generations."""
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg and hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    meta = msg.usage_metadata
                    self.total_input += meta.get("input_tokens", 0)
                    self.total_output += meta.get("output_tokens", 0)
                    details = meta.get("input_token_details", {})
                    if details:
                        self.cache_read += details.get("cache_read", 0)
                        self.cache_creation += details.get("cache_creation", 0)

        cost_summary = self.get_cost_summary()
        logger.info(
            "cost_tracked",
            user_id=self.user_id,
            **cost_summary,
        )

    def get_cost_summary(self) -> dict[str, Any]:
        """Calculate cost with model-aware pricing.

        Returns dict with token counts and total cost in USD.
        Selects pricing based on model_name; falls back to Haiku 4.5 pricing.
        """
        pricing = _resolve_pricing(self.model_name)
        base_input = max(0, self.total_input - self.cache_read - self.cache_creation)
        cost_usd = (
            base_input * pricing["input"] / 1_000_000
            + self.cache_read * pricing["cache_read"] / 1_000_000
            + self.cache_creation * pricing["cache_creation"] / 1_000_000
            + self.total_output * pricing["output"] / 1_000_000
        )
        return {
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
            "cache_read_tokens": self.cache_read,
            "cache_creation_tokens": self.cache_creation,
            "cost_usd": round(cost_usd, 6),
        }
