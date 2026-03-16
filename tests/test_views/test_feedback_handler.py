"""Tests for feedback webhook handler (Story 6.1, AC #2, #3, #5)."""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.views import should_process_event


class TestShouldProcessInteractive:
    """Tests for should_process_event with interactive messages (AC #2)."""

    def _make_entry(self, button_id: str, button_title: str) -> dict:
        """Create a webhook entry with an interactive button_reply."""
        return {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.interactive1",
                                "timestamp": "1710500000",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {
                                        "id": button_id,
                                        "title": button_title,
                                    },
                                },
                            }
                        ]
                    }
                }
            ]
        }

    def test_extracts_interactive_button_reply(self):
        """AC2: should_process_event extrai interactive/button_reply."""
        entry = self._make_entry("feedback_positive", "Útil")
        messages = should_process_event(entry)

        assert len(messages) == 1
        msg = messages[0]
        assert msg["message_type"] == "interactive"
        assert msg["phone"] == "5511999999999"
        assert msg["message_id"] == "wamid.interactive1"

    def test_extracts_button_reply_id(self):
        """AC2: Dados do button_reply disponíveis no resultado."""
        entry = self._make_entry("feedback_negative", "Não útil")
        messages = should_process_event(entry)

        msg = messages[0]
        assert msg["button_reply_id"] == "feedback_negative"
        assert msg["button_reply_title"] == "Não útil"

    def test_interactive_coexists_with_text(self):
        """Interactive e text messages podem coexistir."""
        entry = {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "5511999999999",
                                "id": "wamid.text1",
                                "timestamp": "1710500000",
                                "type": "text",
                                "text": {"body": "Olá"},
                            },
                            {
                                "from": "5511999999999",
                                "id": "wamid.btn1",
                                "timestamp": "1710500001",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {
                                        "id": "feedback_positive",
                                        "title": "Útil",
                                    },
                                },
                            },
                        ]
                    }
                }
            ]
        }
        messages = should_process_event(entry)
        assert len(messages) == 2
        types = [m["message_type"] for m in messages]
        assert "text" in types
        assert "interactive" in types


@pytest.mark.django_db(transaction=True)
class TestHandleFeedback:
    """Tests for handle_feedback function (AC #2, #3)."""

    @pytest.fixture
    async def user(self):
        from workflows.models import User

        return await User.objects.acreate(phone="5511999999999")

    @pytest.fixture
    async def assistant_message(self, user):
        from workflows.models import Message

        return await Message.objects.acreate(user=user, content="Resposta", role="assistant")

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_positive_feedback_saves_to_db(self, mock_send, user, assistant_message):
        """AC2: Clique em 'Útil' salva feedback positivo no banco."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_positive")

        from workflows.models import Feedback

        fb = await Feedback.objects.afirst()
        assert fb is not None
        assert fb.rating == "positive"
        assert fb.user_id == user.pk
        assert fb.message_id == assistant_message.pk
        mock_send.assert_called_once()

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_negative_feedback_saves_to_db(self, mock_send, user, assistant_message):
        """AC2: Clique em 'Não útil' salva feedback negativo."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_negative")

        from workflows.models import Feedback

        fb = await Feedback.objects.afirst()
        assert fb is not None
        assert fb.rating == "negative"

    @patch("workflows.views.set_pending_comment", new_callable=AsyncMock)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_comment_button_sets_pending_state(
        self, mock_send, mock_set_pending, user, assistant_message
    ):
        """AC3: Clique em 'Comentar' salva feedback e seta estado pending."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_comment")

        from workflows.models import Feedback

        fb = await Feedback.objects.afirst()
        assert fb is not None
        assert fb.rating == "comment"  # "Comentar" uses neutral rating, not negative
        assert fb.comment is None  # Comment not yet provided
        mock_set_pending.assert_called_once_with("5511999999999", fb.pk)
        # Should send comment prompt
        mock_send.assert_called_once()

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_feedback_thanks_message_sent(self, mock_send, user, assistant_message):
        """AC2: Sistema responde com confirmação curta."""
        from workflows.views import handle_feedback

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_feedback("5511999999999", "feedback_positive")

        mock_send.assert_called_once()
        sent_text = mock_send.call_args.args[1]
        assert len(sent_text) > 0  # Non-empty thanks message

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_feedback_no_user_does_not_crash(self, mock_send):
        """Edge case: Usuário não encontrado não causa crash."""
        from workflows.views import handle_feedback

        # No user with this phone
        await handle_feedback("5599000000000", "feedback_positive")
        # Should not raise, best-effort


@pytest.mark.django_db(transaction=True)
class TestHandlePendingComment:
    """Tests for pending comment flow (AC #5)."""

    @pytest.fixture
    async def user(self):
        from workflows.models import User

        return await User.objects.acreate(phone="5511999999999")

    @pytest.fixture
    async def feedback_with_pending(self, user):
        from workflows.models import Feedback, Message

        msg = await Message.objects.acreate(user=user, content="Resposta", role="assistant")
        return await Feedback.objects.acreate(message=msg, user=user, rating="negative")

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_pending_comment_saves_text(self, mock_send, user, feedback_with_pending):
        """AC5: Mensagem de texto salva como comentário do feedback pendente."""
        from workflows.views import handle_pending_comment

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        result = await handle_pending_comment(
            "5511999999999", feedback_with_pending.pk, "Ótima resposta!"
        )

        assert result is True
        from workflows.models import Feedback

        fb = await Feedback.objects.aget(pk=feedback_with_pending.pk)
        assert fb.comment == "Ótima resposta!"
        mock_send.assert_called_once()

    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_pending_comment_sends_thanks(self, mock_send, user, feedback_with_pending):
        """AC5: Sistema responde 'Obrigado pelo comentário!'."""
        from workflows.views import handle_pending_comment

        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        await handle_pending_comment("5511999999999", feedback_with_pending.pk, "Boa explicação")

        mock_send.assert_called_once()
        sent_text = mock_send.call_args.args[1]
        assert len(sent_text) > 0

    @pytest.mark.django_db(transaction=True)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_pending_comment_invalid_feedback_id(self, mock_send):
        """Edge case: feedback_id não existe retorna False."""
        from workflows.views import handle_pending_comment

        result = await handle_pending_comment("5511999999999", 99999, "Comentário")

        assert result is False


class TestPendingCommentRedis:
    """Tests for Redis pending comment state (AC #3, #5)."""

    @patch("workflows.views.get_redis_client")
    async def test_set_pending_comment(self, mock_redis_factory):
        """AC3: set_pending_comment salva no Redis com TTL."""
        from workflows.views import set_pending_comment

        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        await set_pending_comment("5511999999999", 42)

        mock_redis.setex.assert_called_once_with("feedback_pending:5511999999999", 300, "42")

    @patch("workflows.views.get_redis_client")
    async def test_get_pending_comment_found(self, mock_redis_factory):
        """AC5: get_pending_comment retorna feedback_id se existe."""
        from workflows.views import get_pending_comment

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "42"
        mock_redis_factory.return_value = mock_redis

        result = await get_pending_comment("5511999999999")

        assert result == 42
        mock_redis.delete.assert_called_once_with("feedback_pending:5511999999999")

    @patch("workflows.views.get_redis_client")
    async def test_get_pending_comment_not_found(self, mock_redis_factory):
        """AC5: get_pending_comment retorna None se não existe."""
        from workflows.views import get_pending_comment

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis_factory.return_value = mock_redis

        result = await get_pending_comment("5511999999999")

        assert result is None

    @patch("workflows.views.get_redis_client")
    async def test_get_pending_comment_clears_key_on_read(self, mock_redis_factory):
        """AC5: get_pending_comment deleta a key Redis ao ler."""
        from workflows.views import get_pending_comment

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "99"
        mock_redis_factory.return_value = mock_redis

        result = await get_pending_comment("5511999999999")

        assert result == 99
        mock_redis.get.assert_called_once_with("feedback_pending:5511999999999")
        mock_redis.delete.assert_called_once_with("feedback_pending:5511999999999")
