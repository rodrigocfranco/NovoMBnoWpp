"""Tests for ConfigService with Redis cache-aside pattern (Story 8.1)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from workflows.models import Config
from workflows.services.config_service import (
    CONFIG_CACHE_PREFIX,
    CONFIG_CACHE_TTL,
    ConfigService,
)
from workflows.utils.errors import ValidationError


@pytest.mark.django_db
class TestConfigServiceGet:
    """Tests for ConfigService.get() with Redis cache layer."""

    async def test_cache_hit_returns_cached_value(self):
        """AC1: Redis cache hit returns value without DB query."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"enabled": True}))

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            result = await ConfigService.get("test:key")

        assert result == {"enabled": True}
        mock_redis.get.assert_awaited_once_with(f"{CONFIG_CACHE_PREFIX}test:key")
        # setex should NOT be called on cache hit
        mock_redis.setex.assert_not_awaited()

    async def test_cache_miss_queries_db_and_populates_cache(self):
        """AC1: Cache miss → DB query → populate Redis cache."""
        await Config.objects.acreate(key="test:miss", value=42, updated_by="test")

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # cache miss
        mock_redis.setex = AsyncMock()

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            result = await ConfigService.get("test:miss")

        assert result == 42
        mock_redis.setex.assert_awaited_once_with(
            f"{CONFIG_CACHE_PREFIX}test:miss",
            CONFIG_CACHE_TTL,
            json.dumps(42),
        )

    async def test_redis_error_on_get_falls_back_to_db(self):
        """AC1: Redis error on get() → graceful degradation to DB."""
        await Config.objects.acreate(key="test:fallback", value="ok", updated_by="test")

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=RedisError("connection refused"))
        mock_redis.setex = AsyncMock()

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            result = await ConfigService.get("test:fallback")

        assert result == "ok"

    async def test_redis_error_on_setex_still_returns_value(self):
        """AC1: Redis error on setex() → value still returned from DB."""
        await Config.objects.acreate(key="test:setfail", value=[1, 2, 3], updated_by="test")

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # cache miss
        mock_redis.setex = AsyncMock(side_effect=RedisError("write error"))

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            result = await ConfigService.get("test:setfail")

        assert result == [1, 2, 3]

    async def test_nonexistent_config_raises_validation_error(self):
        """Existing behavior preserved: nonexistent key raises ValidationError."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            with pytest.raises(ValidationError, match="Config not found: no:exist"):
                await ConfigService.get("no:exist")

    async def test_cache_miss_real_db_query(self):
        """AC1: cache miss uses real DB (no over-mocking)."""
        await Config.objects.acreate(key="test:real", value={"enabled": True}, updated_by="test")

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            result = await ConfigService.get("test:real")

        assert result == {"enabled": True}


@pytest.mark.django_db
class TestConfigServiceInvalidate:
    """Tests for ConfigService.invalidate()."""

    async def test_invalidate_deletes_cache_key(self):
        """AC3: invalidate() deletes Redis cache key."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            await ConfigService.invalidate("rate_limit:free")

        mock_redis.delete.assert_awaited_once_with(f"{CONFIG_CACHE_PREFIX}rate_limit:free")

    async def test_invalidate_redis_error_does_not_raise(self):
        """AC1: Redis error on invalidate → graceful degradation (no exception)."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=RedisError("connection refused"))

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            # Should not raise
            await ConfigService.invalidate("rate_limit:free")
