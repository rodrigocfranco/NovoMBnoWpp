"""Tests for rate_limit node and check_rate_limit edge function (AC1-AC5)."""

from unittest.mock import AsyncMock, patch

from workflows.services.rate_limiter import RateLimitResult
from workflows.whatsapp.nodes.rate_limit import check_rate_limit, rate_limit


def _make_state(**overrides) -> dict:
    """Create a minimal WhatsAppState-like dict for testing."""
    state = {
        "phone_number": "5511999999999",
        "user_message": "Olá",
        "message_type": "text",
        "media_url": None,
        "wamid": "wamid.test",
        "user_id": "user-1",
        "subscription_tier": "free",
        "is_new_user": False,
        "messages": [],
        "formatted_response": "",
        "additional_responses": [],
        "response_sent": False,
        "trace_id": "trace-test",
        "cost_usd": 0.0,
        "retrieved_sources": [],
        "cited_source_indices": [],
        "web_sources": [],
        "transcribed_text": "",
        "rate_limit_exceeded": False,
        "remaining_daily": 0,
        "rate_limit_warning": "",
    }
    state.update(overrides)
    return state


class TestRateLimitNode:
    """Tests for rate_limit graph node."""

    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    async def test_returns_not_exceeded_when_within_limit(self, mock_limiter):
        """AC1: nó rate_limit retorna rate_limit_exceeded=False quando dentro do limite."""
        mock_limiter.check = AsyncMock(
            return_value=RateLimitResult(allowed=True, remaining_daily=8, daily_limit=10, reason="")
        )

        result = await rate_limit(_make_state())

        assert result["rate_limit_exceeded"] is False
        assert result["remaining_daily"] == 8
        assert result["rate_limit_warning"] == ""

    @patch("workflows.whatsapp.nodes.rate_limit.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    async def test_exceeded_daily_sends_message(self, mock_limiter, mock_config, mock_send):
        """AC3: nó rate_limit retorna exceeded=True e envia mensagem quando limite excedido."""
        mock_limiter.check = AsyncMock(
            return_value=RateLimitResult(
                allowed=False, remaining_daily=0, daily_limit=10, reason="daily_exceeded"
            )
        )
        mock_config.get = AsyncMock(
            return_value="Você atingiu seu limite de {limit} interações por hoje. Até lá!"
        )
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        result = await rate_limit(_make_state())

        assert result["rate_limit_exceeded"] is True
        assert result["remaining_daily"] == 0
        mock_send.assert_awaited_once()
        sent_msg = mock_send.call_args[0][1]
        assert "10" in sent_msg  # limit is formatted into message

    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    async def test_returns_warning_when_near_limit(self, mock_limiter, mock_config):
        """AC2: nó rate_limit retorna rate_limit_warning quando próximo do limite."""
        mock_limiter.check = AsyncMock(
            return_value=RateLimitResult(allowed=True, remaining_daily=2, daily_limit=10, reason="")
        )
        # Return warning threshold = 2
        mock_config.get = AsyncMock(return_value=2)

        result = await rate_limit(_make_state())

        assert result["rate_limit_exceeded"] is False
        assert result["remaining_daily"] == 2
        assert "⚠️" in result["rate_limit_warning"]
        assert "2" in result["rate_limit_warning"]

    @patch("workflows.whatsapp.nodes.rate_limit.send_text_message", new_callable=AsyncMock)
    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    async def test_burst_exceeded_sends_burst_message(self, mock_limiter, mock_config, mock_send):
        """AC4: nó rate_limit envia mensagem de burst quando token bucket vazio."""
        mock_limiter.check = AsyncMock(
            return_value=RateLimitResult(
                allowed=False, remaining_daily=0, daily_limit=10, reason="burst_exceeded"
            )
        )
        mock_config.get = AsyncMock(return_value="Muitas mensagens em sequência. Aguarde 1 minuto.")
        mock_send.return_value = {"messages": [{"id": "wamid.sent"}]}

        result = await rate_limit(_make_state())

        assert result["rate_limit_exceeded"] is True
        mock_send.assert_awaited_once()
        sent_msg = mock_send.call_args[0][1]
        assert "Aguarde" in sent_msg

    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    async def test_returns_last_question_warning_when_remaining_zero(
        self,
        mock_limiter,
        mock_config,
    ):
        """AC2: warning especial quando remaining_daily=0 (última pergunta do dia)."""
        mock_limiter.check = AsyncMock(
            return_value=RateLimitResult(allowed=True, remaining_daily=0, daily_limit=10, reason="")
        )
        mock_config.get = AsyncMock(return_value=2)

        result = await rate_limit(_make_state())

        assert result["rate_limit_exceeded"] is False
        assert result["remaining_daily"] == 0
        assert "⚠️" in result["rate_limit_warning"]
        assert "última pergunta" in result["rate_limit_warning"]

    @patch("workflows.whatsapp.nodes.rate_limit.ConfigService")
    @patch("workflows.whatsapp.nodes.rate_limit.RateLimiter")
    async def test_returns_singular_warning_when_remaining_one(self, mock_limiter, mock_config):
        """AC2: warning com singular quando remaining_daily=1."""
        mock_limiter.check = AsyncMock(
            return_value=RateLimitResult(allowed=True, remaining_daily=1, daily_limit=10, reason="")
        )
        mock_config.get = AsyncMock(return_value=2)

        result = await rate_limit(_make_state())

        assert result["rate_limit_exceeded"] is False
        assert result["remaining_daily"] == 1
        assert "⚠️" in result["rate_limit_warning"]
        assert "1 pergunta " in result["rate_limit_warning"]
        assert "1 perguntas" not in result["rate_limit_warning"]


class TestCheckRateLimitEdge:
    """Tests for check_rate_limit conditional edge function."""

    def test_returns_end_when_exceeded(self):
        """AC5: check_rate_limit() retorna END quando exceeded."""
        state = _make_state(rate_limit_exceeded=True)
        result = check_rate_limit(state)
        assert result == "__end__"

    def test_returns_process_media_when_allowed(self):
        """AC5: check_rate_limit() retorna 'process_media' quando allowed."""
        state = _make_state(rate_limit_exceeded=False)
        result = check_rate_limit(state)
        assert result == "process_media"
