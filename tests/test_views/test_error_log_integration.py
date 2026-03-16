"""Tests for ErrorLog creation in views.py error handlers (Story 7.3, AC #3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from workflows.models import ErrorLog, User
from workflows.utils.errors import GraphNodeError


@pytest.mark.django_db(transaction=True)
class TestErrorLogInViews:
    """Verify ErrorLog.acreate() is called in _process_message error handlers."""

    @pytest.fixture
    def validated_data(self):
        return {
            "phone": "5511999990001",
            "message_id": "wamid.err001",
            "timestamp": "1710000000",
            "message_type": "text",
            "body": "Olá",
            "media_id": None,
            "mime_type": None,
        }

    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999990001")

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.get_graph")
    async def test_error_log_created_on_graph_node_error(
        self, mock_get_graph, mock_send, mock_get_handler, mock_propagate, validated_data, user
    ):
        """AC3: GraphNodeError cria ErrorLog com node e error_type corretos."""
        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=GraphNodeError("orchestrate_llm", "LLM timeout"))
        mock_get_graph.return_value = mock_graph

        structlog.contextvars.bind_contextvars(trace_id="trace-gne-001")
        try:
            from workflows.views import _process_message

            await _process_message(validated_data)
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")

        error_log = await ErrorLog.objects.afirst()
        assert error_log is not None
        assert error_log.node == "orchestrate_llm"
        assert error_log.error_type == "GraphNodeError"
        assert error_log.trace_id == "trace-gne-001"
        assert error_log.user_id == user.pk

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.get_graph")
    async def test_error_log_created_on_generic_exception(
        self, mock_get_graph, mock_send, mock_get_handler, mock_propagate, validated_data, user
    ):
        """AC3: Exception genérica cria ErrorLog com node='unknown'."""
        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Unexpected failure"))
        mock_get_graph.return_value = mock_graph

        structlog.contextvars.bind_contextvars(trace_id="trace-gen-002")
        try:
            from workflows.views import _process_message

            await _process_message(validated_data)
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")

        error_log = await ErrorLog.objects.afirst()
        assert error_log is not None
        assert error_log.node == "unknown"
        assert error_log.error_type == "RuntimeError"
        assert error_log.trace_id == "trace-gen-002"

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.get_graph")
    @patch("workflows.models.ErrorLog.objects")
    async def test_fallback_not_blocked_by_errorlog_db_failure(
        self,
        mock_errorlog_mgr,
        mock_get_graph,
        mock_send,
        mock_get_handler,
        mock_propagate,
        validated_data,
    ):
        """CRÍTICO: Falha ao criar ErrorLog NÃO bloqueia envio de fallback."""
        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=GraphNodeError("orchestrate_llm", "LLM timeout"))
        mock_get_graph.return_value = mock_graph

        # Simulate DB failure when creating ErrorLog
        mock_errorlog_mgr.acreate = AsyncMock(side_effect=Exception("DB connection lost"))

        from workflows.views import _process_message

        await _process_message(validated_data)

        # Fallback message MUST still be sent despite ErrorLog failure
        mock_send.assert_awaited()

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.get_graph")
    async def test_error_log_truncates_long_message(
        self, mock_get_graph, mock_send, mock_get_handler, mock_propagate, validated_data, user
    ):
        """ErrorLog trunca error_message em 1000 chars."""
        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        long_msg = "x" * 2000
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=GraphNodeError("orchestrate_llm", long_msg))
        mock_get_graph.return_value = mock_graph

        from workflows.views import _process_message

        await _process_message(validated_data)

        error_log = await ErrorLog.objects.afirst()
        assert error_log is not None
        assert len(error_log.error_message) <= 1000

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    @patch("workflows.views.get_graph")
    async def test_error_log_user_none_when_phone_not_found(
        self, mock_get_graph, mock_send, mock_get_handler, mock_propagate, validated_data
    ):
        """ErrorLog.user é None quando phone não existe no banco."""
        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            side_effect=GraphNodeError("identify_user", "Phone not found")
        )
        mock_get_graph.return_value = mock_graph

        from workflows.views import _process_message

        await _process_message(validated_data)

        error_log = await ErrorLog.objects.afirst()
        assert error_log is not None
        assert error_log.user is None
