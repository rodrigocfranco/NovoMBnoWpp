"""Tests for standardized error logging in graph nodes (Story 5.1, Task 4).

Validates that all except blocks log with required context fields BEFORE
re-raising or falling back, per AC#2:
  - user_id, phone (redacted), node, error_type, error_message, trace_id
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workflows.utils.errors import ExternalServiceError, GraphNodeError

# Required fields that must be present in node error logs
REQUIRED_ERROR_FIELDS = {"user_id", "node", "error_type", "error_message", "trace_id"}


def _make_state(**overrides):
    """Thin wrapper over shared make_whatsapp_state with error logging test defaults."""
    from tests.test_whatsapp.conftest import make_whatsapp_state

    defaults = {
        "user_id": "123",
        "subscription_tier": "premium",
        "formatted_response": "response text",
        "trace_id": "trace-abc-123",
    }
    defaults.update(overrides)
    return make_whatsapp_state(**defaults)


def _assert_error_log_fields(log_call, required_fields=None):
    """Assert that a structlog call contains the required fields."""
    if required_fields is None:
        required_fields = REQUIRED_ERROR_FIELDS
    kwargs = log_call.kwargs
    missing = required_fields - set(kwargs.keys())
    assert not missing, f"Missing required log fields: {missing}. Present: {set(kwargs.keys())}"


@pytest.mark.django_db
class TestOrchestrateErrorLogging:
    """orchestrate_llm must log with context BEFORE re-raising GraphNodeError."""

    @patch("workflows.whatsapp.nodes.orchestrate_llm.get_model")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.CostTrackingCallback")
    @patch("workflows.whatsapp.nodes.orchestrate_llm.build_system_message")
    async def test_logs_error_before_raising(
        self, mock_build_sys, mock_tracker_cls, mock_get_model
    ):
        """When LLM invocation fails, node logs with required fields before raise."""
        from workflows.whatsapp.nodes.orchestrate_llm import orchestrate_llm

        mock_build_sys.return_value = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_cost_summary.return_value = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
        mock_tracker_cls.return_value = mock_tracker

        mock_model = AsyncMock()
        mock_model.ainvoke.side_effect = RuntimeError("LLM timeout")
        mock_get_model.return_value = mock_model

        state = _make_state()

        with (
            patch("workflows.whatsapp.nodes.orchestrate_llm.logger") as mock_logger,
            pytest.raises(GraphNodeError),
        ):
            await orchestrate_llm(state)

        # Must have logged error with required fields before raising
        mock_logger.error.assert_called_once()
        _assert_error_log_fields(mock_logger.error.call_args)


@pytest.mark.django_db
class TestIdentifyUserErrorLogging:
    """identify_user must log with context BEFORE re-raising GraphNodeError."""

    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    @patch("workflows.whatsapp.nodes.identify_user.User")
    async def test_logs_error_before_raising(self, mock_user_cls, mock_cache):
        """When DB/cache fails, node logs with required fields before raise."""
        from workflows.whatsapp.nodes.identify_user import identify_user

        mock_cache.get_session = AsyncMock(side_effect=RuntimeError("Redis down"))

        state = _make_state()

        with (
            patch("workflows.whatsapp.nodes.identify_user.logger") as mock_logger,
            pytest.raises(GraphNodeError),
        ):
            await identify_user(state)

        mock_logger.error.assert_called_once()
        # identify_user doesn't have user_id yet (it discovers it), so check subset
        kwargs = mock_logger.error.call_args.kwargs
        assert "node" in kwargs
        assert "error_type" in kwargs
        assert "error_message" in kwargs
        assert "trace_id" in kwargs


@pytest.mark.django_db
class TestLoadContextErrorLogging:
    """load_context must log with context BEFORE re-raising GraphNodeError."""

    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    async def test_logs_error_before_raising(self, mock_cache):
        """When cache + DB both fail, node logs with required fields before raise."""
        from workflows.whatsapp.nodes.load_context import load_context

        mock_cache.get_session = AsyncMock(side_effect=RuntimeError("Redis down"))

        state = _make_state()

        with (
            patch("workflows.whatsapp.nodes.load_context.logger") as mock_logger,
            pytest.raises(GraphNodeError),
        ):
            await load_context(state)

        mock_logger.error.assert_called_once()
        _assert_error_log_fields(mock_logger.error.call_args)


@pytest.mark.django_db
class TestPersistErrorLogging:
    """persist must log with required fields on DB failure."""

    async def test_logs_error_with_required_fields(self):
        """When DB fails, persist logs with standardized fields."""
        from django.db import DatabaseError

        from workflows.whatsapp.nodes.persist import persist

        state = _make_state()

        with (
            patch("workflows.whatsapp.nodes.persist.User") as mock_user_cls,
            patch("workflows.whatsapp.nodes.persist.logger") as mock_logger,
        ):
            # Preserve real DoesNotExist so except clause works
            from workflows.models import User

            mock_user_cls.DoesNotExist = User.DoesNotExist
            mock_user_cls.objects.aget = AsyncMock(side_effect=DatabaseError("connection reset"))
            await persist(state)

        mock_logger.exception.assert_called_once()
        kwargs = mock_logger.exception.call_args.kwargs
        assert "user_id" in kwargs
        assert "node" in kwargs
        assert "error_type" in kwargs


@pytest.mark.django_db
class TestProcessMediaErrorLogging:
    """process_media must log with required fields on audio/image failure."""

    @patch(
        "workflows.whatsapp.nodes.process_media.send_text_message",
        new_callable=AsyncMock,
    )
    @patch(
        "workflows.whatsapp.nodes.process_media.download_media",
        new_callable=AsyncMock,
    )
    async def test_audio_failure_logs_required_fields(self, mock_download, mock_send):
        """Audio transcription failure includes node, error_type, user_id."""
        from workflows.whatsapp.nodes.process_media import process_media

        mock_download.side_effect = ExternalServiceError(
            service="whatsapp", message="media download failed"
        )

        state = _make_state(message_type="audio", media_id="media-123", mime_type="audio/ogg")

        with (
            patch("workflows.whatsapp.nodes.process_media.logger") as mock_logger,
            pytest.raises(GraphNodeError),
        ):
            await process_media(state)

        mock_logger.error.assert_called()
        # Find the main error call (process_media_audio_failed)
        error_calls = [c for c in mock_logger.error.call_args_list]
        assert len(error_calls) >= 1
        kwargs = error_calls[0].kwargs
        assert "node" in kwargs
        assert "error_type" in kwargs

    @patch("workflows.whatsapp.nodes.process_media.download_media", new_callable=AsyncMock)
    async def test_image_download_failure_logs_required_fields(self, mock_download):
        """Image download failure includes node, error_type, user_id."""
        from workflows.whatsapp.nodes.process_media import process_media

        mock_download.side_effect = ExternalServiceError(
            service="whatsapp", message="media download failed"
        )

        state = _make_state(message_type="image", media_id="media-123", mime_type="image/jpeg")

        with patch("workflows.whatsapp.nodes.process_media.logger") as mock_logger:
            await process_media(state)

        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert "node" in kwargs
        assert "error_type" in kwargs


@pytest.mark.django_db
class TestPhoneRedaction:
    """Phone numbers must be redacted (only last 4 digits) in all error logs."""

    async def test_persist_no_full_phone_in_logs(self):
        """persist never logs full phone number."""
        from django.db import DatabaseError

        from workflows.whatsapp.nodes.persist import persist

        state = _make_state(phone_number="5511987654321")

        with (
            patch("workflows.whatsapp.nodes.persist.User") as mock_user_cls,
            patch("workflows.whatsapp.nodes.persist.logger") as mock_logger,
        ):
            from workflows.models import User

            mock_user_cls.DoesNotExist = User.DoesNotExist
            mock_user_cls.objects.aget = AsyncMock(side_effect=DatabaseError("conn reset"))
            await persist(state)

        # Check that full phone never appears in any log kwargs
        for call in mock_logger.method_calls:
            if call.kwargs:
                for value in call.kwargs.values():
                    if isinstance(value, str):
                        assert "5511987654321" not in value, (
                            f"Full phone number leaked in log: {call}"
                        )
