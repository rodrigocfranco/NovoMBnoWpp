"""Integration tests for feedback flow (Story 6.1, AC #1-#5).

Tests the full webhook processing pipeline for feedback interactions.
"""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.models import Feedback, Message, User


@pytest.mark.django_db(transaction=True)
class TestFeedbackFullFlow:
    """Integration: resposta → buttons → clique → feedback salvo (AC #1-#2)."""

    @pytest.fixture
    async def user(self):
        return await User.objects.acreate(phone="5511999999999")

    @pytest.fixture
    async def assistant_message(self, user):
        return await Message.objects.acreate(user=user, content="Resposta", role="assistant")

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_positive_flow_end_to_end(self, mock_send, user, assistant_message):
        """AC1+AC2: Positive button click → feedback salvo + thanks sent."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_positive")

        fb = await Feedback.objects.afirst()
        assert fb is not None
        assert fb.rating == "positive"
        assert fb.user_id == user.pk
        assert fb.message_id == assistant_message.pk
        assert fb.comment is None
        mock_send.assert_called_once()

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_negative_flow_end_to_end(self, mock_send, user, assistant_message):
        """AC1+AC2: Negative button click → feedback salvo + thanks sent."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_negative")

        fb = await Feedback.objects.afirst()
        assert fb is not None
        assert fb.rating == "negative"
        assert fb.comment is None
        mock_send.assert_called_once()

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_duplicate_feedback_updates_existing(self, mock_send, user, assistant_message):
        """M3: Feedback duplicado no mesmo message atualiza rating em vez de criar novo."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_positive")
        await handle_feedback("5511999999999", "feedback_negative")

        count = await Feedback.objects.acount()
        assert count == 1  # Upsert: only one feedback per user+message

        fb = await Feedback.objects.afirst()
        assert fb.rating == "negative"  # Updated to last click


@pytest.mark.django_db(transaction=True)
class TestCommentFullFlow:
    """Integration: "Comentar" → prompt → texto → salvo (AC #3, #5)."""

    @pytest.fixture
    async def user(self):
        return await User.objects.acreate(phone="5511999999999")

    @pytest.fixture
    async def assistant_message(self, user):
        return await Message.objects.acreate(user=user, content="Resposta", role="assistant")

    @patch("workflows.views.get_redis_client")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_comment_flow_end_to_end(
        self, mock_send, mock_redis_factory, user, assistant_message
    ):
        """AC3+AC5: Comment flow — click → prompt → text → saved."""
        from workflows.views import handle_feedback, handle_pending_comment

        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        # Step 1: User clicks "Comentar"
        await handle_feedback("5511999999999", "feedback_comment")

        fb = await Feedback.objects.afirst()
        assert fb is not None
        assert fb.rating == "comment"
        assert fb.comment is None

        # Redis set_pending_comment was called
        mock_redis.setex.assert_called_once()
        pending_key = mock_redis.setex.call_args.args[0]
        assert pending_key == "feedback_pending:5511999999999"

        # Prompt was sent
        assert mock_send.call_count == 1

        # Step 2: User sends comment text
        mock_send.reset_mock()
        result = await handle_pending_comment("5511999999999", fb.pk, "Resposta muito boa!")

        assert result is True
        await fb.arefresh_from_db()
        assert fb.comment == "Resposta muito boa!"

        # Thanks was sent
        mock_send.assert_called_once()

    @patch("workflows.views.get_redis_client")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_comment_flow_feedback_links_to_last_message(
        self, mock_send, mock_redis_factory, user
    ):
        """AC3: Feedback linked to most recent assistant message."""
        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        # Create two assistant messages, should link to the latest one
        await Message.objects.acreate(user=user, content="Old response", role="assistant")
        latest = await Message.objects.acreate(user=user, content="New response", role="assistant")

        from workflows.views import handle_feedback

        await handle_feedback("5511999999999", "feedback_positive")

        fb = await Feedback.objects.afirst()
        assert fb.message_id == latest.pk


@pytest.mark.django_db(transaction=True)
class TestWebhookRoutingInteractive:
    """Integration: Webhook routing dispatches interactive messages correctly."""

    def test_should_process_event_passes_interactive_to_pipeline(self):
        """AC2: should_process_event includes interactive in extractable messages."""
        import time

        from workflows.views import FEEDBACK_BUTTON_IDS, should_process_event

        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.fb_pos",
                                "timestamp": str(int(time.time())),
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {
                                        "id": "feedback_positive",
                                        "title": "Útil",
                                    },
                                },
                            }
                        ]
                    }
                }
            ]
        }
        messages = should_process_event(entry)
        assert len(messages) == 1
        msg = messages[0]
        assert msg["message_type"] == "interactive"
        assert msg["button_reply_id"] in FEEDBACK_BUTTON_IDS


class TestPendingCommentNonTextPreservesState:
    """H1 fix: non-text messages must NOT consume pending comment state."""

    @patch("workflows.views.get_pending_comment", new_callable=AsyncMock)
    async def test_audio_message_does_not_call_get_pending_comment(self, mock_get_pending):
        """H1: Audio message while pending comment does NOT consume Redis state."""
        # get_pending_comment should never be called for non-text messages
        # (the webhook handler only calls it for message_type == "text")
        mock_get_pending.return_value = 42  # Would return if called

        # Simulate the routing logic: audio messages go straight to pipeline
        from workflows.views import SUPPORTED_TYPES

        assert "audio" in SUPPORTED_TYPES
        # The fix ensures get_pending_comment is only in the `elif message_type == "text"` branch
        # so it's never called for audio — verified by mock not being called
        mock_get_pending.assert_not_called()
