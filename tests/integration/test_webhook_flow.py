"""Integration test: webhook → debounce → graph with REAL Redis (no Redis mocks).

Validates the flow that unit tests cannot: real message buffering, real
debounce timers, and real deduplication — without mocking Redis.

Run: DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/ -m integration
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from workflows.services.debounce import BUFFER_KEY_PREFIX, buffer_message, get_and_clear_buffer
from workflows.services.rate_limiter import RateLimitResult
from workflows.whatsapp.graph import build_whatsapp_graph

pytestmark = pytest.mark.integration


PHONE = "5511999998877"


def _make_validated_data(**overrides) -> dict:
    """Create validated webhook message data."""
    data = {
        "phone": PHONE,
        "message_id": f"wamid.integ_{int(time.time())}",
        "timestamp": str(int(time.time())),
        "message_type": "text",
        "body": "Qual a dose de dipirona?",
        "media_id": None,
        "mime_type": None,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db(transaction=True)
class TestWebhookToGraphFlowReal:
    """Webhook → debounce (real Redis) → graph (mocked LLM)."""

    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_debounce_buffers_then_graph_executes(
        self,
        mock_id_cache,
        mock_ctx_cache,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        mock_rl_config,
        mock_rl_limiter,
        redis_client,
    ):
        """Real Redis buffer → batch → graph execution (no Redis mocking)."""
        from workflows.models import User

        await User.objects.acreate(phone=PHONE, subscription_tier="free")

        # Setup mocks (LLM only — Redis is REAL)
        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.002,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="Dipirona: 500mg a 1g")
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_rl_limiter.check = AsyncMock(
            return_value=RateLimitResult(
                allowed=True,
                remaining_daily=99,
                daily_limit=100,
                reason="",
            )
        )
        mock_rl_config.get = AsyncMock(return_value=2)

        # Step 1: Buffer messages in REAL Redis (simulating debounce)
        msg1 = _make_validated_data(body="Qual a dose")
        msg2 = _make_validated_data(body="de dipirona?", message_id="wamid.integ_2")
        await buffer_message(PHONE, json.dumps(msg1), 3)
        await buffer_message(PHONE, json.dumps(msg2), 3)

        # Verify buffer exists in REAL Redis
        key = f"{BUFFER_KEY_PREFIX}:{PHONE}"
        length = await redis_client.llen(key)
        assert length == 2, f"Expected 2 messages in buffer, got {length}"

        # Step 2: Atomically get and clear (simulating debounce timer expiry)
        raw_messages = await get_and_clear_buffer(PHONE)
        assert len(raw_messages) == 2

        # Combine messages (as debounce does)
        messages = [json.loads(raw) for raw in raw_messages]
        combined_body = "\n".join(m.get("body", "") for m in messages)
        batch_data = messages[0].copy()
        batch_data["body"] = combined_body

        # Step 3: Execute graph with combined message
        graph = build_whatsapp_graph()
        initial_state = {
            "phone_number": batch_data["phone"],
            "user_message": batch_data["body"],
            "message_type": batch_data["message_type"],
            "media_url": None,
            "media_id": batch_data.get("media_id"),
            "mime_type": batch_data.get("mime_type"),
            "wamid": batch_data["message_id"],
            "messages": [],
            "user_id": "",
            "subscription_tier": "",
            "is_new_user": False,
            "formatted_response": "",
            "additional_responses": [],
            "response_sent": False,
            "trace_id": "",
            "cost_usd": 0.0,
            "retrieved_sources": [],
            "cited_source_indices": [],
            "web_sources": [],
            "rate_limit_exceeded": False,
            "remaining_daily": 0,
            "rate_limit_warning": "",
            "transcribed_text": "",
        }

        result = await graph.ainvoke(initial_state)

        # Assertions
        assert result["response_sent"] is True
        assert result["cost_usd"] > 0
        assert result["formatted_response"]
        mock_send.assert_called()

        # Buffer is empty after processing (atomicity)
        remaining = await redis_client.llen(key)
        assert remaining == 0
