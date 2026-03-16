"""Integration test: process_media node with REAL Redis + PostgreSQL.

Mocks only the Whisper API (httpx response). Uses real:
- Redis (rate limiter, deduplication)
- PostgreSQL (User model, Message model)

Run: DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/ -m integration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from workflows.whatsapp.graph import build_whatsapp_graph

pytestmark = pytest.mark.integration

PHONE = "5511999998811"


def _make_initial_state(**overrides) -> dict:
    """Create a complete initial state for graph invocation."""
    state = {
        "phone_number": PHONE,
        "user_message": "",
        "message_type": "audio",
        "media_url": None,
        "media_id": "media-integration-001",
        "mime_type": "audio/ogg; codecs=opus",
        "wamid": "wamid.integration_pm",
        "messages": [],
        "user_id": "",
        "subscription_tier": "",
        "is_new_user": False,
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "trace-pm-int-001",
        "cost_usd": 0.0,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
        "transcribed_text": "",
        "image_message": None,
        "provider_used": "",
    }
    state.update(overrides)
    return state


@pytest.mark.django_db(transaction=True)
class TestProcessMediaIntegration:
    """Integration tests for process_media node within full graph."""

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    @patch("workflows.whatsapp.nodes.process_media.transcribe_audio", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.process_media.download_media", new_callable=AsyncMock)
    async def test_audio_flows_through_full_pipeline(
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
        """Audio message: download → transcribe → LLM → format → send → persist (real Redis+PG)."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone=PHONE, subscription_tier="premium")

        mock_download.return_value = (b"ogg-audio-data", "audio/ogg")
        mock_transcribe.return_value = "O que é sepse neonatal?"

        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 150,
            "output_tokens": 80,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.002,
        }
        mock_tracker_cls.return_value = mock_tracker
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(
            content="Sepse neonatal é uma infecção sistêmica grave no recém-nascido."
        )
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_get_model.return_value = mock_model
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.pm_int"}]}

        graph = build_whatsapp_graph()
        result = await graph.ainvoke(_make_initial_state())

        # Transcription worked
        assert result["transcribed_text"] == "O que é sepse neonatal?"
        assert result["user_message"] == "O que é sepse neonatal?"

        # Full pipeline completed
        assert result["response_sent"] is True
        assert "sepse" in result["formatted_response"].lower()

        # Messages persisted in REAL PostgreSQL
        msg_count = await Message.objects.filter(user=user).acount()
        assert msg_count == 2

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    @patch("workflows.whatsapp.nodes.process_media.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.process_media.transcribe_audio", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.process_media.download_media", new_callable=AsyncMock)
    async def test_audio_whisper_failure_stops_pipeline(
        self,
        mock_download,
        mock_transcribe,
        mock_pm_send,
        mock_id_cache,
        mock_ctx_cache,
        mock_tracker_cls,
        mock_get_model,
        mock_mark,
        mock_send,
        redis_client,
    ):
        """Whisper failure: sends error message, raises GraphNodeError, LLM never called."""
        from workflows.models import User
        from workflows.utils.errors import GraphNodeError

        phone = "5511999998822"
        await User.objects.acreate(phone=phone, subscription_tier="free")

        mock_download.return_value = (b"bad-audio", "audio/ogg")
        mock_transcribe.side_effect = Exception("Whisper API unreachable")
        mock_pm_send.return_value = {"messages": [{"id": "wamid.err"}]}

        mock_id_cache.get_session = AsyncMock(return_value=None)
        mock_id_cache.cache_session = AsyncMock()
        mock_ctx_cache.get_session = AsyncMock(return_value=None)
        mock_ctx_cache.cache_session = AsyncMock()
        mock_tracker_cls.return_value = MagicMock()
        mock_get_model.return_value = AsyncMock()
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.x"}]}

        graph = build_whatsapp_graph()

        with pytest.raises(GraphNodeError):
            await graph.ainvoke(_make_initial_state(phone_number=phone, wamid="wamid.fail_int"))

        # Error message sent to user
        mock_pm_send.assert_awaited_once()
        sent_msg = mock_pm_send.call_args[0][1]
        assert "Não consegui processar seu áudio" in sent_msg

        # LLM was never called (cost saving)
        mock_get_model.return_value.ainvoke.assert_not_called()
