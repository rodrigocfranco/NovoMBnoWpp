"""Tests for FeatureFlagService — hash-based bucketing (Story 10.1)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from workflows.models import Config
from workflows.services.config_service import ConfigService
from workflows.services.feature_flags import is_feature_enabled


@pytest.fixture()
def mock_redis_client():
    """Mock Redis client with cache-miss default (returns None on get)."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock()
    with patch("workflows.services.config_service.get_redis_client", return_value=mock):
        yield mock


@pytest.mark.django_db
class TestFeatureFlagDeterminism:
    """AC1: Same user always gets same treatment."""

    async def test_same_user_same_result(self, mock_redis_client):
        """Same user_id + same rollout_percentage = same result, always."""
        await Config.objects.acreate(
            key="feature_flag:test_det",
            value={"rollout_percentage": 50},
            updated_by="test",
        )
        results = [await is_feature_enabled("user123", "test_det") for _ in range(10)]
        assert len(set(results)) == 1  # All identical

    async def test_determinism_different_users_same_percentage(self, mock_redis_client):
        """Different users may get different results, but each is deterministic."""
        await Config.objects.acreate(
            key="feature_flag:test_det2",
            value={"rollout_percentage": 50},
            updated_by="test",
        )
        result_a1 = await is_feature_enabled("userA", "test_det2")
        result_a2 = await is_feature_enabled("userA", "test_det2")
        result_b1 = await is_feature_enabled("userB", "test_det2")
        result_b2 = await is_feature_enabled("userB", "test_det2")

        assert result_a1 == result_a2
        assert result_b1 == result_b2


@pytest.mark.django_db
class TestFeatureFlagDistribution:
    """AC1: Hash-based bucketing provides uniform distribution."""

    async def test_uniform_distribution_at_50_percent(self, mock_redis_client):
        """With 1000 random user_ids and rollout=50, ~50% ±5% should be True."""
        await Config.objects.acreate(
            key="feature_flag:test_dist",
            value={"rollout_percentage": 50},
            updated_by="test",
        )
        results = [await is_feature_enabled(f"user_{i}", "test_dist") for i in range(1000)]
        enabled_count = sum(results)
        assert 450 <= enabled_count <= 550, f"Expected ~500, got {enabled_count}"


@pytest.mark.django_db
class TestFeatureFlagRolloutBoundaries:
    """AC3: Rollout 0% and 100% edge cases."""

    async def test_rollout_zero_all_false(self, mock_redis_client):
        """rollout_percentage=0 → 100% returns False (all traffic to n8n)."""
        await Config.objects.acreate(
            key="feature_flag:test_zero",
            value={"rollout_percentage": 0},
            updated_by="test",
        )
        results = [await is_feature_enabled(f"user_{i}", "test_zero") for i in range(100)]
        assert all(r is False for r in results)

    async def test_rollout_100_all_true(self, mock_redis_client):
        """rollout_percentage=100 → 100% returns True (all traffic to new pipeline)."""
        await Config.objects.acreate(
            key="feature_flag:test_100",
            value={"rollout_percentage": 100},
            updated_by="test",
        )
        results = [await is_feature_enabled(f"user_{i}", "test_100") for i in range(100)]
        assert all(r is True for r in results)


@pytest.mark.django_db
class TestFeatureFlagCacheInteraction:
    """AC5: Cache hit/miss scenarios via ConfigService."""

    async def test_cache_hit_uses_cached_config(self, mock_redis_client):
        """Redis cache hit → config loaded from cache, not DB."""
        mock_redis_client.get = AsyncMock(return_value=json.dumps({"rollout_percentage": 100}))
        result = await is_feature_enabled("anyuser", "test_cache")
        assert result is True

    async def test_cache_miss_queries_db(self, mock_redis_client):
        """Redis cache miss → falls back to DB."""
        await Config.objects.acreate(
            key="feature_flag:test_cmiss",
            value={"rollout_percentage": 100},
            updated_by="test",
        )
        result = await is_feature_enabled("anyuser", "test_cmiss")
        assert result is True


@pytest.mark.django_db
class TestFeatureFlagRedisDown:
    """AC5: Redis failure graceful degradation."""

    async def test_redis_down_returns_false_when_no_db_config(self, mock_redis_client):
        """Redis down + no DB config → safe default False."""
        mock_redis_client.get = AsyncMock(side_effect=RedisError("connection refused"))
        result = await is_feature_enabled("anyuser", "nonexistent_feature")
        assert result is False

    async def test_redis_down_falls_back_to_db(self, mock_redis_client):
        """Redis down + DB has config → uses DB value."""
        await Config.objects.acreate(
            key="feature_flag:test_redisdown",
            value={"rollout_percentage": 100},
            updated_by="test",
        )
        mock_redis_client.get = AsyncMock(side_effect=RedisError("connection refused"))
        mock_redis_client.setex = AsyncMock(side_effect=RedisError("connection refused"))
        result = await is_feature_enabled("anyuser", "test_redisdown")
        assert result is True


@pytest.mark.django_db
class TestFeatureFlagConfigErrors:
    """AC5: Config missing and invalid type scenarios."""

    async def test_config_not_found_returns_false(self, mock_redis_client):
        """Feature flag config doesn't exist → safe default False."""
        result = await is_feature_enabled("anyuser", "nonexistent")
        assert result is False

    async def test_config_invalid_type_returns_false(self, mock_redis_client):
        """Config value is not a dict → safe default False."""
        await Config.objects.acreate(
            key="feature_flag:test_invalid",
            value="not_a_dict",
            updated_by="test",
        )
        result = await is_feature_enabled("anyuser", "test_invalid")
        assert result is False

    async def test_config_missing_rollout_percentage_returns_false(self, mock_redis_client):
        """Config dict without rollout_percentage → defaults to 0 → False."""
        await Config.objects.acreate(
            key="feature_flag:test_norollout",
            value={"description": "no percentage"},
            updated_by="test",
        )
        result = await is_feature_enabled("anyuser", "test_norollout")
        assert result is False

    async def test_config_negative_rollout_returns_false(self, mock_redis_client):
        """Negative rollout_percentage → treated as 0 → False."""
        await Config.objects.acreate(
            key="feature_flag:test_neg",
            value={"rollout_percentage": -10},
            updated_by="test",
        )
        result = await is_feature_enabled("anyuser", "test_neg")
        assert result is False

    async def test_config_rollout_percentage_string_returns_false(self, mock_redis_client):
        """rollout_percentage as string → invalid type → False."""
        await Config.objects.acreate(
            key="feature_flag:test_strpct",
            value={"rollout_percentage": "fifty"},
            updated_by="test",
        )
        result = await is_feature_enabled("anyuser", "test_strpct")
        assert result is False


@pytest.mark.django_db
class TestFeatureFlagAdminInvalidation:
    """Task 4.1: Admin save → cache invalidation → feature flag returns new result."""

    async def test_admin_save_cache_invalidation_flow(self):
        """E2E: admin save rollout_percentage → cache invalidated → new result."""
        cache_store: dict[str, str] = {}

        async def mock_get(key):
            return cache_store.get(key)

        async def mock_setex(key, ttl, value):
            cache_store[key] = value

        async def mock_delete(key):
            cache_store.pop(key, None)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.setex = AsyncMock(side_effect=mock_setex)
        mock_redis.delete = AsyncMock(side_effect=mock_delete)

        with patch("workflows.services.config_service.get_redis_client", return_value=mock_redis):
            # 1. Create config with rollout=100 (all users enabled)
            config = await Config.objects.acreate(
                key="feature_flag:test_admin_flow",
                value={"rollout_percentage": 100},
                updated_by="admin",
            )

            # 2. Feature flag enabled for all users
            assert await is_feature_enabled("anyuser", "test_admin_flow") is True

            # 3. "Admin" rolls back to 0%
            config.value = {"rollout_percentage": 0}
            await config.asave()

            # 4. Stale cache → still returns True
            assert await is_feature_enabled("anyuser", "test_admin_flow") is True

            # 5. Cache invalidation (triggered by admin save_model)
            await ConfigService.invalidate("feature_flag:test_admin_flow")

            # 6. After invalidation → reads new DB value → False
            assert await is_feature_enabled("anyuser", "test_admin_flow") is False
