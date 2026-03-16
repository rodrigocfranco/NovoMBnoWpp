"""Tests for ConfigAdmin with audit trail and cache invalidation (Story 8.1)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import sync_to_async

from workflows.admin import ConfigAdmin, ConfigHistoryAdmin, ConfigHistoryInline
from workflows.models import Config, ConfigHistory
from workflows.services.config_service import ConfigService


@pytest.mark.django_db
class TestConfigAdminSaveModel:
    """Tests for ConfigAdmin.save_model() audit trail and cache invalidation."""

    def _make_request(self, username="admin"):
        request = MagicMock()
        request.user.username = username
        return request

    def test_save_model_sets_updated_by(self):
        """AC2: save_model auto-populates updated_by with request.user.username."""
        config = Config.objects.create(key="test:admin", value=10, updated_by="old_user")
        request = self._make_request("new_admin")
        form = MagicMock()

        admin_instance = ConfigAdmin(Config, MagicMock())
        admin_instance.save_model(request, config, form, change=True)

        config.refresh_from_db()
        assert config.updated_by == "new_admin"

    def test_save_model_creates_config_history(self):
        """AC2: save_model creates ConfigHistory with old_value and new_value."""
        config = Config.objects.create(key="test:history", value=10, updated_by="admin")
        request = self._make_request("admin")
        form = MagicMock()

        # Change value
        config.value = 15
        admin_instance = ConfigAdmin(Config, MagicMock())
        admin_instance.save_model(request, config, form, change=True)

        history = ConfigHistory.objects.filter(config=config).first()
        assert history is not None
        assert history.old_value == 10
        assert history.new_value == 15
        assert history.changed_by == "admin"

    def test_save_model_new_config_has_null_old_value(self):
        """AC2: New config creates ConfigHistory with old_value=None."""
        config = Config(key="test:new", value="hello", updated_by="")
        request = self._make_request("admin")
        form = MagicMock()

        admin_instance = ConfigAdmin(Config, MagicMock())
        admin_instance.save_model(request, config, form, change=False)

        history = ConfigHistory.objects.filter(config=config).first()
        assert history is not None
        assert history.old_value is None
        assert history.new_value == "hello"

    @patch("workflows.admin.ConfigService")
    def test_save_model_invalidates_redis_cache(self, mock_config_service):
        """AC3: save_model invalidates Redis cache key after save."""
        mock_config_service.invalidate = AsyncMock()
        config = Config.objects.create(key="test:invalidate", value=10, updated_by="admin")
        request = self._make_request("admin")
        form = MagicMock()

        config.value = 15
        admin_instance = ConfigAdmin(Config, MagicMock())
        admin_instance.save_model(request, config, form, change=True)

        mock_config_service.invalidate.assert_called_once_with("test:invalidate")

    @patch("workflows.admin.ConfigService")
    def test_save_model_cache_invalidation_failure_does_not_raise(self, mock_config_service):
        """AC3: Redis failure on invalidation does not break admin save."""
        mock_config_service.invalidate = AsyncMock(side_effect=Exception("Redis down"))
        config = Config.objects.create(key="test:fail", value=1, updated_by="admin")
        request = self._make_request("admin")
        form = MagicMock()

        admin_instance = ConfigAdmin(Config, MagicMock())
        # Should not raise
        admin_instance.save_model(request, config, form, change=True)

        # Config should still be saved
        config.refresh_from_db()
        assert config.updated_by == "admin"


@pytest.mark.django_db
class TestConfigAdminConfiguration:
    """Tests for ConfigAdmin readonly_fields, inlines, and ConfigHistoryAdmin."""

    def test_readonly_fields_include_updated_at_and_updated_by(self):
        """AC4: updated_at and updated_by are readonly in admin."""
        admin_instance = ConfigAdmin(Config, MagicMock())
        assert "updated_at" in admin_instance.readonly_fields
        assert "updated_by" in admin_instance.readonly_fields

    def test_config_history_inline_present(self):
        """AC4: ConfigHistoryInline is registered in ConfigAdmin."""
        admin_instance = ConfigAdmin(Config, MagicMock())
        assert ConfigHistoryInline in admin_instance.inlines

    def test_config_history_inline_is_readonly(self):
        """AC4: ConfigHistoryInline does not allow adding or deleting."""
        inline = ConfigHistoryInline(Config, MagicMock())
        assert inline.can_delete is False
        assert inline.has_add_permission(MagicMock()) is False

    def test_config_history_admin_is_immutable(self):
        """AC4: ConfigHistoryAdmin does not allow add, change, or delete."""
        admin_instance = ConfigHistoryAdmin(ConfigHistory, MagicMock())
        request = MagicMock()
        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_change_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False


@pytest.mark.django_db
class TestConfigAdminE2E:
    """E2E test: admin save → cache invalidated → ConfigService.get() returns new value."""

    def _make_request(self, username="admin"):
        request = MagicMock()
        request.user.username = username
        return request

    async def test_admin_save_invalidates_cache_and_get_returns_new_value(self):
        """Task 3.1 E2E: admin save → cache invalidated → next get() returns new value."""
        # 1. Create config with initial value
        config = await Config.objects.acreate(key="test:e2e", value=10, updated_by="admin")

        # 2. Simulate cache populated by first get()
        mock_redis = AsyncMock()
        cached_values = {}

        async def mock_get(key):
            return cached_values.get(key)

        async def mock_setex(key, ttl, value):
            cached_values[key] = value

        async def mock_delete(key):
            cached_values.pop(key, None)

        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.setex = AsyncMock(side_effect=mock_setex)
        mock_redis.delete = AsyncMock(side_effect=mock_delete)

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            # First get() populates cache
            result = await ConfigService.get("test:e2e")
            assert result == 10
            assert "config:test:e2e" in cached_values

            # 3. Admin save changes value and invalidates cache
            config.value = 99
            request = self._make_request("admin")
            admin_instance = ConfigAdmin(Config, MagicMock())

            with patch("workflows.admin.get_redis_client", return_value=mock_redis):
                await sync_to_async(admin_instance.save_model)(
                    request, config, MagicMock(), change=True
                )

            # 4. Cache should be invalidated
            assert "config:test:e2e" not in cached_values

            # 5. Next get() should return NEW value from DB
            result = await ConfigService.get("test:e2e")
            assert result == 99
