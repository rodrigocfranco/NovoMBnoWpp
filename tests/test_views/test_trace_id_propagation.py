"""Tests for trace_id propagation from middleware to graph state (Story 7.2, AC #2)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog


class TestTraceIdPropagation:
    """Verify trace_id from TraceIDMiddleware reaches initial_state."""

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.get_graph")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_trace_id_from_contextvars_in_initial_state(
        self, mock_send, mock_get_graph, mock_get_handler, mock_propagate
    ):
        """AC2: trace_id do middleware aparece no initial_state do graph."""
        expected_trace_id = str(uuid.uuid4())

        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"user_id": "u1", "response_sent": True})
        mock_get_graph.return_value = mock_graph

        structlog.contextvars.bind_contextvars(trace_id=expected_trace_id)
        try:
            from workflows.views import _process_message

            validated_data = {
                "phone": "5511999990000",
                "message_id": "wamid.test123",
                "timestamp": "1710000000",
                "message_type": "text",
                "body": "Olá",
                "media_id": None,
                "mime_type": None,
            }
            await _process_message(validated_data)

            mock_graph.ainvoke.assert_called_once()
            call_args = mock_graph.ainvoke.call_args
            initial_state = call_args[0][0]

            assert initial_state["trace_id"] == expected_trace_id
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")

    @pytest.mark.asyncio
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler", return_value=None)
    @patch("workflows.views.get_graph")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_trace_id_fallback_generates_uuid(
        self, mock_send, mock_get_graph, mock_get_handler, mock_propagate
    ):
        """AC2: Se trace_id não estiver no contextvars, gera UUID novo."""
        structlog.contextvars.unbind_contextvars("trace_id")

        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"user_id": "u1", "response_sent": True})
        mock_get_graph.return_value = mock_graph

        from workflows.views import _process_message

        validated_data = {
            "phone": "5511999990000",
            "message_id": "wamid.test456",
            "timestamp": "1710000000",
            "message_type": "text",
            "body": "Olá",
            "media_id": None,
            "mime_type": None,
        }
        await _process_message(validated_data)

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        trace_id = initial_state["trace_id"]

        # Must be a valid UUID string, not empty
        assert trace_id != ""
        uuid.UUID(trace_id)  # Raises if invalid
