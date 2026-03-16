"""Tests for send_whatsapp node (AC3, AC4)."""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.whatsapp.nodes.send_whatsapp import send_whatsapp

_MOD = "workflows.whatsapp.nodes.send_whatsapp"


def _make_state(**overrides) -> dict:
    """Create a minimal WhatsAppState-like dict for testing."""
    state = {
        "phone_number": "5511999999999",
        "user_message": "Olá",
        "message_type": "text",
        "media_url": None,
        "wamid": "wamid.test",
        "user_id": "1",
        "subscription_tier": "free",
        "is_new_user": False,
        "messages": [],
        "formatted_response": "Resposta formatada.",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "trace-test",
        "cost_usd": 0.001,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
    }
    state.update(overrides)
    return state


class TestSendWhatsAppNode:
    """Tests for send_whatsapp graph node."""

    @pytest.fixture(autouse=True)
    def _mock_buttons(self):
        with patch(
            "workflows.whatsapp.nodes.send_whatsapp.send_interactive_buttons",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = {"messages": [{"id": "wamid.btn"}]}
            yield mock

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_calls_mark_as_read_and_send(self, mock_mark, mock_send):
        """AC3: send_whatsapp chama mark_as_read e send_text_message."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        state = _make_state()
        result = await send_whatsapp(state)

        mock_mark.assert_called_once_with("wamid.test")
        mock_send.assert_called_once_with("5511999999999", "Resposta formatada.")
        assert result["response_sent"] is True

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_sends_additional_responses_sequentially(self, mock_mark, mock_send):
        """AC3: Múltiplas respostas enviadas sequencialmente."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        state = _make_state(
            formatted_response="Parte 1",
            additional_responses=["Parte 2", "Parte 3"],
        )
        result = await send_whatsapp(state)

        assert mock_send.call_count == 3
        calls = [call.args for call in mock_send.call_args_list]
        assert calls[0] == ("5511999999999", "Parte 1")
        assert calls[1] == ("5511999999999", "Parte 2")
        assert calls[2] == ("5511999999999", "Parte 3")
        assert result["response_sent"] is True

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_returns_response_sent_true_on_success(self, mock_mark, mock_send):
        """AC3: Retorna response_sent=True em sucesso."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        state = _make_state()
        result = await send_whatsapp(state)

        assert result == {"response_sent": True}

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_mark_as_read_failure_does_not_block(self, mock_mark, mock_send):
        """AC3: Falha no mark_as_read não bloqueia envio."""
        mock_mark.return_value = False  # fire-and-forget failure
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        state = _make_state()
        result = await send_whatsapp(state)

        mock_send.assert_called_once()
        assert result["response_sent"] is True

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_main_send_failure_raises_for_retry(self, mock_mark, mock_send):
        """AC4: ExternalServiceError propaga para RetryPolicy fazer retry."""
        from workflows.utils.errors import ExternalServiceError

        mock_mark.return_value = True
        mock_send.side_effect = ExternalServiceError(service="whatsapp", message="HTTP 500")

        state = _make_state()
        with pytest.raises(ExternalServiceError):
            await send_whatsapp(state)

    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_additional_response_failure_is_best_effort(self, mock_mark, mock_send):
        """M5: Falha em additional_response não impede retorno de sucesso."""
        from workflows.utils.errors import ExternalServiceError

        mock_mark.return_value = True
        # Main send succeeds, then second call (first additional) fails
        mock_send.side_effect = [
            {"messages": [{"id": "wamid.sent1"}]},
            ExternalServiceError(service="whatsapp", message="HTTP 503"),
        ]

        state = _make_state(
            formatted_response="Parte 1",
            additional_responses=["Parte 2", "Parte 3"],
        )
        result = await send_whatsapp(state)

        # Main message sent successfully, additional failed — still returns True
        assert result["response_sent"] is True
        # Only 2 calls: main + first additional (which failed, so stops)
        assert mock_send.call_count == 2


class TestSendWhatsAppWelcome:
    """Tests for welcome message (AC3, AC4)."""

    @pytest.fixture(autouse=True)
    def _mock_buttons(self):
        with patch(
            "workflows.whatsapp.nodes.send_whatsapp.send_interactive_buttons",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = {"messages": [{"id": "wamid.btn"}]}
            yield mock

    @patch("workflows.whatsapp.nodes.send_whatsapp.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_new_user_receives_welcome_before_response(
        self,
        mock_mark,
        mock_send,
        mock_config,
    ):
        """AC3: is_new_user=True → envia welcome message ANTES da resposta."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_config.get = AsyncMock(return_value="Bem-vindo!")

        state = _make_state(is_new_user=True)
        result = await send_whatsapp(state)

        assert mock_send.call_count == 2
        calls = [call.args for call in mock_send.call_args_list]
        assert calls[0] == ("5511999999999", "Bem-vindo!")
        assert calls[1] == ("5511999999999", "Resposta formatada.")
        assert result["response_sent"] is True

    @patch("workflows.whatsapp.nodes.send_whatsapp.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_existing_user_no_welcome(self, mock_mark, mock_send, mock_config):
        """AC4: is_new_user=False → NÃO envia welcome message."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        state = _make_state(is_new_user=False)
        result = await send_whatsapp(state)

        mock_send.assert_called_once_with("5511999999999", "Resposta formatada.")
        # ConfigService.get is NOT called for welcome (only for feedback prompt)
        welcome_calls = [
            c for c in mock_config.get.call_args_list if c.args == ("message:welcome",)
        ]
        assert len(welcome_calls) == 0
        assert result["response_sent"] is True

    @patch("workflows.whatsapp.nodes.send_whatsapp.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_welcome_from_config_service(self, mock_mark, mock_send, mock_config):
        """AC3: Welcome message vem do ConfigService."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_config.get = AsyncMock(return_value="Texto customizado do admin!")

        state = _make_state(is_new_user=True)
        await send_whatsapp(state)

        welcome_calls = [
            c for c in mock_config.get.call_args_list if c.args == ("message:welcome",)
        ]
        assert len(welcome_calls) == 1
        calls = [call.args for call in mock_send.call_args_list]
        assert calls[0] == ("5511999999999", "Texto customizado do admin!")

    @patch("workflows.whatsapp.nodes.send_whatsapp.ConfigService")
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_config_failure_uses_default_welcome(self, mock_mark, mock_send, mock_config):
        """AC3: ConfigService falha → usa texto default hardcoded."""
        from workflows.whatsapp.nodes.send_whatsapp import DEFAULT_WELCOME_MESSAGE

        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))

        state = _make_state(is_new_user=True)
        result = await send_whatsapp(state)

        calls = [call.args for call in mock_send.call_args_list]
        assert calls[0] == ("5511999999999", DEFAULT_WELCOME_MESSAGE)
        assert calls[1] == ("5511999999999", "Resposta formatada.")
        assert result["response_sent"] is True


class TestSendWhatsAppFeedbackButtons:
    """Tests for feedback buttons sent after response (Story 6.1, AC #1)."""

    @patch(f"{_MOD}.send_interactive_buttons", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_sends_feedback_buttons_after_response(self, mock_mark, mock_send, mock_buttons):
        """AC1: Feedback buttons enviados após resposta principal."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_buttons.return_value = {"messages": [{"id": "wamid.btn"}]}

        state = _make_state()
        result = await send_whatsapp(state)

        mock_send.assert_called_once()
        mock_buttons.assert_called_once()
        call_args = mock_buttons.call_args
        assert call_args.args[0] == "5511999999999"
        assert result["response_sent"] is True

    @patch(f"{_MOD}.send_interactive_buttons", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_feedback_buttons_contain_three_options(self, mock_mark, mock_send, mock_buttons):
        """AC1: 3 opções de feedback: Útil, Não útil, Comentar."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_buttons.return_value = {"messages": [{"id": "wamid.btn"}]}

        state = _make_state()
        await send_whatsapp(state)

        buttons_arg = mock_buttons.call_args.args[2]
        assert len(buttons_arg) == 3
        button_ids = [b["id"] for b in buttons_arg]
        assert "feedback_positive" in button_ids
        assert "feedback_negative" in button_ids
        assert "feedback_comment" in button_ids

    @patch(f"{_MOD}.send_interactive_buttons", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_feedback_buttons_failure_is_best_effort(
        self, mock_mark, mock_send, mock_buttons
    ):
        """AC1: Falha no envio de buttons não bloqueia resposta."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_buttons.side_effect = Exception("Button send failed")

        state = _make_state()
        result = await send_whatsapp(state)

        assert result["response_sent"] is True
        mock_send.assert_called_once()

    @patch(f"{_MOD}.send_interactive_buttons", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.send_whatsapp.mark_as_read", new_callable=AsyncMock)
    async def test_feedback_buttons_sent_after_additional_responses(
        self, mock_mark, mock_send, mock_buttons
    ):
        """AC1: Buttons enviados após additional_responses."""
        mock_mark.return_value = True
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}
        mock_buttons.return_value = {"messages": [{"id": "wamid.btn"}]}

        state = _make_state(
            formatted_response="Parte 1",
            additional_responses=["Parte 2"],
        )
        result = await send_whatsapp(state)

        assert mock_send.call_count == 2
        mock_buttons.assert_called_once()
        assert result["response_sent"] is True
