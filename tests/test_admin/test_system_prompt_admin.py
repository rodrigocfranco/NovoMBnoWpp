"""Tests for SystemPromptVersionAdmin (AC: #2, #3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

from workflows.admin import SystemPromptVersionAdmin
from workflows.models import SystemPromptVersion


@pytest.mark.django_db
class TestSystemPromptVersionAdmin:
    @pytest.fixture(autouse=True)
    def _setup(self):
        """Deactivate seed version and set up admin."""
        SystemPromptVersion.objects.filter(is_active=True).update(is_active=False)
        self.admin = SystemPromptVersionAdmin(SystemPromptVersion, MagicMock())

    def _make_request(self, username="testadmin"):
        request = MagicMock()
        request.user.username = username
        request.user.email = f"{username}@medway.com"
        return request

    def test_admin_registered(self):
        from django.contrib.admin import site

        assert SystemPromptVersion in site._registry

    def test_list_display(self):
        assert "pk" in self.admin.list_display
        assert "author" in self.admin.list_display
        assert "is_active" in self.admin.list_display
        assert "content_preview" in self.admin.list_display
        assert "created_at" in self.admin.list_display

    def test_content_preview_short(self):
        obj = SystemPromptVersion(content="Short content", author="test")
        assert self.admin.content_preview(obj) == "Short content"

    def test_content_preview_truncated(self):
        obj = SystemPromptVersion(content="x" * 200, author="test")
        preview = self.admin.content_preview(obj)
        assert preview.endswith("...")
        assert len(preview) == 103  # 100 chars + "..."

    @patch("workflows.admin._invalidate_prompt_cache")
    def test_activate_version_success(self, mock_invalidate):
        """AC3: Ação 'Ativar' desativa todas e ativa a selecionada."""
        v1 = SystemPromptVersion.objects.create(content="v1", author="system", is_active=True)
        v2 = SystemPromptVersion.objects.create(content="v2", author="admin", is_active=False)

        request = self._make_request()
        queryset = SystemPromptVersion.objects.filter(pk=v2.pk)

        self.admin.activate_version(request, queryset)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True
        mock_invalidate.assert_called_once()

    @patch("workflows.admin._invalidate_prompt_cache")
    def test_activate_version_rejects_multiple(self, mock_invalidate):
        """AC3: Selecionar mais de uma versão mostra erro."""
        SystemPromptVersion.objects.create(content="v1", author="a", is_active=False)
        SystemPromptVersion.objects.create(content="v2", author="b", is_active=False)

        request = self._make_request()
        queryset = SystemPromptVersion.objects.all()

        self.admin.activate_version(request, queryset)

        mock_invalidate.assert_not_called()

    @patch("workflows.admin._invalidate_prompt_cache")
    def test_save_model_auto_author(self, mock_invalidate):
        """AC2: save_model auto-preenche author a partir de request.user."""
        obj = SystemPromptVersion(content="new prompt", author="", is_active=False)
        request = self._make_request(username="rodrigo")
        form = MagicMock()
        self.admin.save_model(request, obj, form, change=False)

        assert obj.author == "rodrigo"

    @patch("workflows.admin._invalidate_prompt_cache")
    def test_save_model_deactivates_previous(self, mock_invalidate):
        """AC2: Salvar versão ativa desativa a anterior."""
        v1 = SystemPromptVersion.objects.create(content="v1", author="system", is_active=True)
        obj = SystemPromptVersion(content="v2", author="admin", is_active=True)
        request = self._make_request()

        self.admin.save_model(request, obj, MagicMock(), change=False)

        v1.refresh_from_db()
        assert v1.is_active is False
        assert obj.is_active is True
        mock_invalidate.assert_called_once()

    @patch("workflows.admin._invalidate_prompt_cache")
    def test_save_model_inactive_no_cache_invalidation(self, mock_invalidate):
        """Salvar versão inativa NÃO invalida cache."""
        obj = SystemPromptVersion(content="draft", author="admin", is_active=False)
        request = self._make_request()

        self.admin.save_model(request, obj, MagicMock(), change=False)

        mock_invalidate.assert_not_called()

    @patch("workflows.admin._invalidate_prompt_cache")
    def test_activate_version_logs_structlog(self, mock_invalidate):
        """AC3: Ativação é registrada em log structlog."""
        v1 = SystemPromptVersion.objects.create(content="v1", author="system", is_active=False)
        request = self._make_request(username="rodrigo")
        queryset = SystemPromptVersion.objects.filter(pk=v1.pk)

        with patch("workflows.admin.logger") as mock_logger:
            self.admin.activate_version(request, queryset)
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs[0][0] == "system_prompt_activated"
            assert call_kwargs[1]["version_id"] == v1.pk
            assert call_kwargs[1]["activated_by"] == "rodrigo"


class TestInvalidatePromptCache:
    """Test _invalidate_prompt_cache helper."""

    @patch("workflows.admin.get_redis_client")
    def test_invalidate_calls_redis_delete(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        from workflows.admin import _invalidate_prompt_cache

        _invalidate_prompt_cache()

        mock_redis.delete.assert_called_once_with("config:system_prompt")

    @patch("workflows.admin.get_redis_client")
    def test_invalidate_handles_redis_error(self, mock_get_redis):
        """Best-effort: Redis error is logged, not raised."""
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = RedisError("connection refused")
        mock_get_redis.return_value = mock_redis

        from workflows.admin import _invalidate_prompt_cache

        # Should not raise
        _invalidate_prompt_cache()
