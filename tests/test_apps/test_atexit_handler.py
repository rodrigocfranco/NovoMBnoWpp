"""Tests for atexit handler registration in WorkflowsConfig (Story 7.2, AC #6)."""

import atexit
from unittest.mock import patch

from django.test import override_settings


class TestAtexitHandler:
    """Verify atexit handler for Langfuse shutdown."""

    @override_settings(LANGFUSE_ENABLED=True)
    @patch("workflows.apps.shutdown_langfuse")
    @patch.object(atexit, "register")
    def test_atexit_registered_when_enabled(self, mock_register, mock_shutdown):
        """AC6: atexit.register chamado com shutdown_langfuse quando habilitado."""
        from workflows.apps import WorkflowsConfig

        config = WorkflowsConfig("workflows", __import__("workflows"))
        config.ready()

        mock_register.assert_called_once_with(mock_shutdown)

    @override_settings(LANGFUSE_ENABLED=False)
    @patch("workflows.apps.shutdown_langfuse")
    @patch.object(atexit, "register")
    def test_atexit_not_registered_when_disabled(self, mock_register, mock_shutdown):
        """AC6: atexit.register NÃO chamado quando LANGFUSE_ENABLED=False."""
        from workflows.apps import WorkflowsConfig

        config = WorkflowsConfig("workflows", __import__("workflows"))
        config.ready()

        # atexit.register should not be called with shutdown_langfuse
        for call in mock_register.call_args_list:
            assert call[0][0] is not mock_shutdown
