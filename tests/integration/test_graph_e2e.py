"""Integration test: full graph E2E with REAL Redis + PostgreSQL (LLM mocked only).

Unlike unit tests, this does NOT mock:
- Redis (rate limiter, deduplication)
- PostgreSQL (User model, Message model)
- ConfigService (falls back to defaults via real Redis miss)

Only mocks: LLM provider, WhatsApp send, CacheManager (no real Supabase)

Run: DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/ -m integration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from workflows.whatsapp.graph import build_whatsapp_graph

pytestmark = pytest.mark.integration


PHONE = "5511999997766"


def _make_initial_state(**overrides) -> dict:
    """Create a complete initial state for graph invocation."""
    state = {
        "phone_number": PHONE,
        "user_message": "O que é hipertensão arterial?",
        "message_type": "text",
        "media_url": None,
        "media_id": None,
        "mime_type": None,
        "wamid": "wamid.e2e_test",
        "messages": [],
        "user_id": "",
        "subscription_tier": "",
        "is_new_user": False,
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "trace-e2e-001",
        "cost_usd": 0.0,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
        "transcribed_text": "",
        "image_message": None,
    }
    state.update(overrides)
    return state


@pytest.mark.django_db(transaction=True)
class TestGraphE2EReal:
    """Full graph execution with real Redis + PostgreSQL."""

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_full_pipeline_with_real_redis_and_postgres(
        self,
        mock_id_cache,
        mock_ctx_cache,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        redis_client,
    ):
        """Graph runs identify → rate_limit(real Redis) → LLM → format → send → persist(real PG)."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone=PHONE, subscription_tier="premium")

        # Mock only LLM + WhatsApp send + CacheManager
        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 200,
            "output_tokens": 100,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.003,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(
            content="Hipertensão arterial é a elevação sustentada da pressão arterial."
        )
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.e2e_sent"}]}

        # Execute graph — rate_limit uses REAL Redis (no mock)
        graph = build_whatsapp_graph()
        result = await graph.ainvoke(_make_initial_state())

        # Pipeline completed
        assert result["response_sent"] is True
        assert result["user_id"] == str(user.id)
        assert result["subscription_tier"] == "premium"
        assert result["rate_limit_exceeded"] is False
        assert result["cost_usd"] == 0.003
        assert "Hipertensão" in result["formatted_response"]

        # Messages persisted in REAL PostgreSQL
        msg_count = await Message.objects.filter(user=user).acount()
        assert msg_count == 2, f"Expected 2 messages (user + assistant), got {msg_count}"

        # WhatsApp send was called
        mock_send.assert_called()

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_rate_limit_blocks_with_real_redis(
        self,
        mock_id_cache,
        mock_ctx_cache,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        redis_client,
    ):
        """Rate limiter with REAL Redis blocks after exceeding burst limit."""
        from workflows.models import User

        phone = "5511999997700"
        await User.objects.acreate(phone=phone, subscription_tier="free")

        # Setup LLM mock (may not be reached if rate limited)
        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.0001,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="OK")
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.rl_test"}]}

        graph = build_whatsapp_graph()

        # Send multiple requests until burst limit kicks in
        # Default burst limit is 5/minute for free tier
        exceeded = False
        for i in range(15):
            result = await graph.ainvoke(
                _make_initial_state(
                    phone_number=phone,
                    wamid=f"wamid.rl_{i}",
                    user_message=f"Message {i}",
                )
            )
            if result["rate_limit_exceeded"]:
                exceeded = True
                break

        assert exceeded, "Rate limiter should have blocked after burst limit (real Redis)"

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    @patch("workflows.whatsapp.nodes.process_media.transcribe_audio", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.process_media.download_media", new_callable=AsyncMock)
    async def test_audio_pipeline_with_real_redis_and_postgres(
        self,
        mock_download,
        mock_transcribe,
        mock_id_cache,
        mock_ctx_cache,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        redis_client,
    ):
        """Graph runs full pipeline with audio: process_media transcribes → LLM receives text."""
        from workflows.models import Message, User

        phone = "5511999997788"
        user = await User.objects.acreate(phone=phone, subscription_tier="premium")

        # Mock media processing
        mock_download.return_value = (b"audio-bytes", "audio/ogg")
        mock_transcribe.return_value = "Qual a dose de amoxicilina pediátrica?"

        # Mock LLM + WhatsApp send + CacheManager
        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 200,
            "output_tokens": 100,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.004,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(
            content="A dose de amoxicilina pediátrica é 50mg/kg/dia."
        )
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.audio_e2e"}]}

        graph = build_whatsapp_graph()
        result = await graph.ainvoke(
            _make_initial_state(
                phone_number=phone,
                message_type="audio",
                media_id="media-e2e-123",
                mime_type="audio/ogg; codecs=opus",
                user_message="",
            )
        )

        # Pipeline completed with transcription
        assert result["response_sent"] is True
        assert result["transcribed_text"] == "Qual a dose de amoxicilina pediátrica?"
        assert result["user_message"] == "Qual a dose de amoxicilina pediátrica?"
        assert "amoxicilina" in result["formatted_response"]

        # Messages persisted
        msg_count = await Message.objects.filter(user=user).acount()
        assert msg_count == 2

        # Whisper was called
        mock_download.assert_awaited_once()
        mock_transcribe.assert_awaited_once()

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    @patch("workflows.whatsapp.nodes.process_media.download_media", new_callable=AsyncMock)
    async def test_image_pipeline_with_real_redis_and_postgres(
        self,
        mock_download,
        mock_id_cache,
        mock_ctx_cache,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        redis_client,
    ):
        """Graph runs full pipeline with image: process_media builds multimodal → LLM Vision."""
        from workflows.models import Message, User

        phone = "5511999997799"
        user = await User.objects.acreate(phone=phone, subscription_tier="premium")

        # Mock media download (fake image bytes, small enough to pass 5MB check)
        fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        mock_download.return_value = (fake_image, "image/jpeg")

        # Mock LLM + WhatsApp send + CacheManager
        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 1600,
            "output_tokens": 200,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.012,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(
            content="Esta é uma questão de anatomia sobre o sistema cardiovascular."
        )
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.image_e2e"}]}

        graph = build_whatsapp_graph()
        result = await graph.ainvoke(
            _make_initial_state(
                phone_number=phone,
                message_type="image",
                media_id="media-img-e2e",
                mime_type="image/jpeg",
                user_message="O que é isso?",
            )
        )

        # Pipeline completed with image
        assert result["response_sent"] is True
        assert result["image_message"] is not None
        assert len(result["image_message"]) == 2
        assert result["image_message"][0]["type"] == "image"
        assert result["image_message"][1]["text"] == "O que é isso?"
        assert "anatomia" in result["formatted_response"]

        # LLM received multimodal HumanMessage
        call_args = mock_model.ainvoke.call_args
        messages = call_args[0][0]
        # Find the HumanMessage with multimodal content
        human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
        assert any(isinstance(m.content, list) for m in human_msgs)

        # Messages persisted
        msg_count = await Message.objects.filter(user=user).acount()
        assert msg_count == 2

        # Download was called
        mock_download.assert_awaited_once_with("media-img-e2e", "image/jpeg")
