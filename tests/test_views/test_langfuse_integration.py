"""Tests for Langfuse integration in graph invoke (Story 7.2, AC #1, #4, #5)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
from django.test import override_settings


class TestLangfuseGraphIntegration:
    """Verify Langfuse handler is passed to graph.ainvoke when enabled."""

    @pytest.mark.asyncio
    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler")
    @patch("workflows.views.get_graph")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_langfuse_handler_in_callbacks(
        self, mock_send, mock_get_graph, mock_get_handler, mock_propagate
    ):
        """AC1: Langfuse CallbackHandler passado no config.callbacks do graph.ainvoke."""
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        # propagate_attributes as context manager
        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"user_id": "u1", "response_sent": True})
        mock_get_graph.return_value = mock_graph

        try:
            from workflows.views import _process_message

            validated_data = {
                "phone": "5511999990000",
                "message_id": "wamid.test789",
                "timestamp": "1710000000",
                "message_type": "text",
                "body": "Olá",
                "media_id": None,
                "mime_type": None,
            }
            await _process_message(validated_data)

            call_args = mock_graph.ainvoke.call_args
            config = call_args[1].get("config") or call_args[0][1]
            assert mock_handler in config["callbacks"]
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")

    @pytest.mark.asyncio
    @override_settings(LANGFUSE_ENABLED=False)
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler")
    @patch("workflows.views.get_graph")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_no_callbacks_when_disabled(
        self, mock_send, mock_get_graph, mock_get_handler, mock_propagate
    ):
        """AC7: Sem callbacks Langfuse quando LANGFUSE_ENABLED=False."""
        mock_get_handler.return_value = None

        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"user_id": "u1", "response_sent": True})
        mock_get_graph.return_value = mock_graph

        from workflows.views import _process_message

        validated_data = {
            "phone": "5511999990000",
            "message_id": "wamid.test000",
            "timestamp": "1710000000",
            "message_type": "text",
            "body": "Olá",
            "media_id": None,
            "mime_type": None,
        }
        await _process_message(validated_data)

        call_args = mock_graph.ainvoke.call_args
        config = call_args[1].get("config") or call_args[0][1]
        # No callbacks key or empty callbacks
        callbacks = config.get("callbacks", [])
        assert len(callbacks) == 0

    @pytest.mark.asyncio
    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler")
    @patch("workflows.views.get_graph")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_propagate_attributes_called_with_metadata(
        self, mock_send, mock_get_graph, mock_get_handler, mock_propagate
    ):
        """AC4: propagate_attributes chamado com trace_id, session_id, tags."""
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "user_id": "user-abc",
                "subscription_tier": "premium",
                "provider_used": "vertex_ai",
                "response_sent": True,
            }
        )
        mock_get_graph.return_value = mock_graph

        try:
            from workflows.views import _process_message

            validated_data = {
                "phone": "5511999990000",
                "message_id": "wamid.testmeta",
                "timestamp": "1710000000",
                "message_type": "text",
                "body": "Olá",
                "media_id": None,
                "mime_type": None,
            }
            await _process_message(validated_data)

            mock_propagate.assert_called_once()
            call_kwargs = mock_propagate.call_args[1]
            assert call_kwargs["session_id"] == "5511999990000"
            assert "whatsapp" in call_kwargs["tags"]
            assert "text" in call_kwargs["tags"]
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")

    @pytest.mark.asyncio
    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.views.update_trace_metadata")
    @patch("workflows.views.propagate_attributes")
    @patch("workflows.views.get_langfuse_handler")
    @patch("workflows.views.get_graph")
    @patch("workflows.views.send_text_message", new_callable=AsyncMock)
    async def test_update_trace_metadata_called_after_invoke(
        self, mock_send, mock_get_graph, mock_get_handler, mock_propagate, mock_update
    ):
        """AC4: update_trace_metadata chamado após ainvoke com user_id e metadata."""
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        mock_propagate.return_value.__enter__ = MagicMock(return_value=None)
        mock_propagate.return_value.__exit__ = MagicMock(return_value=False)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "user_id": "user-abc",
                "subscription_tier": "premium",
                "provider_used": "vertex_ai",
                "response_sent": True,
            }
        )
        mock_get_graph.return_value = mock_graph

        try:
            from workflows.views import _process_message

            validated_data = {
                "phone": "5511999990000",
                "message_id": "wamid.testupdate",
                "timestamp": "1710000000",
                "message_type": "text",
                "body": "Olá",
                "media_id": None,
                "mime_type": None,
            }
            await _process_message(validated_data)

            mock_update.assert_called_once_with(
                trace_id=trace_id,
                user_id="user-abc",
                metadata={
                    "subscription_tier": "premium",
                    "provider_used": "vertex_ai",
                },
            )
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")
