"""Tests for CacheManager (session cache Redis)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from workflows.services.cache_manager import CacheManager

SESSION_TTL = 3600


class TestCacheManager:
    """Tests for Redis session cache operations."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        client = AsyncMock()
        with patch("workflows.services.cache_manager._get_redis_client", return_value=client):
            yield client

    async def test_cache_session_stores_data(self, mock_redis):
        """cache_session armazena dados com key session:{user_id} e TTL 1h."""
        data = {"user_id": "42", "subscription_tier": "premium"}
        await CacheManager.cache_session("42", data)

        mock_redis.set.assert_awaited_once_with(
            "session:42",
            json.dumps(data),
            ex=SESSION_TTL,
        )

    async def test_get_session_returns_data_on_hit(self, mock_redis):
        """get_session retorna dados quando cache hit."""
        expected = {"user_id": "42", "subscription_tier": "free"}
        mock_redis.get.return_value = json.dumps(expected)

        result = await CacheManager.get_session("42")

        assert result == expected
        mock_redis.get.assert_awaited_once_with("session:42")

    async def test_get_session_returns_none_on_miss(self, mock_redis):
        """get_session retorna None quando cache miss."""
        mock_redis.get.return_value = None

        result = await CacheManager.get_session("42")

        assert result is None

    async def test_invalidate_session_deletes_key(self, mock_redis):
        """invalidate_session remove cache da sessão."""
        await CacheManager.invalidate_session("42")

        mock_redis.delete.assert_awaited_once_with("session:42")

    async def test_cache_session_handles_redis_error(self, mock_redis):
        """cache_session loga erro mas não levanta exceção se Redis falhar."""
        mock_redis.set.side_effect = Exception("Redis connection lost")

        # Should not raise
        await CacheManager.cache_session("42", {"user_id": "42"})

    async def test_get_session_handles_redis_error(self, mock_redis):
        """get_session retorna None se Redis falhar."""
        mock_redis.get.side_effect = Exception("Redis connection lost")

        result = await CacheManager.get_session("42")

        assert result is None
