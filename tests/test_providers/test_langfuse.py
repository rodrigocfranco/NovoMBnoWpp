"""Tests for Langfuse provider (Story 7.2, AC #1, #4, #6)."""

from unittest.mock import MagicMock, patch

from django.test import override_settings


class TestGetLangfuseHandler:
    """Tests for get_langfuse_handler() factory function."""

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.providers.langfuse.CallbackHandler")
    def test_returns_callback_handler(self, mock_handler_cls):
        """AC1: get_langfuse_handler() retorna CallbackHandler do Langfuse."""
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        from workflows.providers.langfuse import get_langfuse_handler

        result = get_langfuse_handler(trace_id="abc-123")

        mock_handler_cls.assert_called_once()
        assert result is mock_handler

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.providers.langfuse.CallbackHandler")
    def test_returns_none_when_disabled(self, mock_handler_cls):
        """AC7: Retorna None quando LANGFUSE_ENABLED=False."""
        with override_settings(LANGFUSE_ENABLED=False):
            from workflows.providers.langfuse import get_langfuse_handler

            result = get_langfuse_handler(trace_id="abc-123")

            assert result is None
            mock_handler_cls.assert_not_called()

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.providers.langfuse.CallbackHandler")
    @patch("workflows.providers.langfuse.logger")
    def test_handler_logs_trace_id(self, mock_logger, mock_handler_cls):
        """AC2: get_langfuse_handler() loga trace_id no debug para correlação."""
        mock_handler_cls.return_value = MagicMock()

        from workflows.providers.langfuse import get_langfuse_handler

        get_langfuse_handler(trace_id="trace-uuid-xyz")

        mock_logger.debug.assert_called_once_with(
            "langfuse_handler_created", trace_id="trace-uuid-xyz"
        )


class TestIsLangfuseEnabled:
    """Tests for is_langfuse_enabled() helper."""

    @override_settings(LANGFUSE_ENABLED=True)
    def test_enabled_when_setting_true(self):
        from workflows.providers.langfuse import is_langfuse_enabled

        assert is_langfuse_enabled() is True

    @override_settings(LANGFUSE_ENABLED=False)
    def test_disabled_when_setting_false(self):
        from workflows.providers.langfuse import is_langfuse_enabled

        assert is_langfuse_enabled() is False


class TestShutdownLangfuse:
    """Tests for shutdown_langfuse() (AC #6)."""

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.providers.langfuse.get_client")
    def test_shutdown_calls_client_shutdown(self, mock_get_client):
        """AC6: shutdown_langfuse() chama get_client().shutdown()."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from workflows.providers.langfuse import shutdown_langfuse

        shutdown_langfuse()

        mock_get_client.assert_called_once()
        mock_client.shutdown.assert_called_once()

    @override_settings(LANGFUSE_ENABLED=False)
    @patch("workflows.providers.langfuse.get_client")
    def test_shutdown_noop_when_disabled(self, mock_get_client):
        """AC6: shutdown_langfuse() não faz nada quando desabilitado."""
        from workflows.providers.langfuse import shutdown_langfuse

        shutdown_langfuse()

        mock_get_client.assert_not_called()


class TestUpdateTraceMetadata:
    """Tests for update_trace_metadata() (AC #4)."""

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.providers.langfuse.get_client")
    def test_updates_trace_with_metadata(self, mock_get_client):
        """AC4: update_trace_metadata() chama client.trace() com user_id e metadata."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from workflows.providers.langfuse import update_trace_metadata

        update_trace_metadata(
            trace_id="trace-123",
            user_id="user-abc",
            metadata={"subscription_tier": "premium", "provider_used": "vertex_ai"},
        )

        mock_client.trace.assert_called_once_with(
            id="trace-123",
            user_id="user-abc",
            metadata={"subscription_tier": "premium", "provider_used": "vertex_ai"},
        )

    @override_settings(LANGFUSE_ENABLED=False)
    @patch("workflows.providers.langfuse.get_client")
    def test_noop_when_disabled(self, mock_get_client):
        """AC4: update_trace_metadata() não faz nada quando desabilitado."""
        from workflows.providers.langfuse import update_trace_metadata

        update_trace_metadata(trace_id="trace-123", user_id="user-abc")

        mock_get_client.assert_not_called()

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.providers.langfuse.get_client")
    @patch("workflows.providers.langfuse.logger")
    def test_handles_exception_gracefully(self, mock_logger, mock_get_client):
        """AC4: Exceção no update não propaga — loga e segue."""
        mock_get_client.side_effect = RuntimeError("connection failed")

        from workflows.providers.langfuse import update_trace_metadata

        update_trace_metadata(trace_id="trace-err", user_id="u1")

        mock_logger.exception.assert_called_once_with(
            "langfuse_trace_update_error", trace_id="trace-err"
        )
