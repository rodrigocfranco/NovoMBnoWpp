"""Tests for RateLimiter service (AC1, AC4)."""

from unittest.mock import AsyncMock, MagicMock, patch

from workflows.services.rate_limiter import RateLimiter


def _mock_pipeline(incr_result: int):
    """Create a mock Redis pipeline that returns incr_result for INCR."""
    pipe = AsyncMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[incr_result, True])
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    return pipe


class TestRateLimiterCheck:
    """Tests for RateLimiter.check() method."""

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_allowed_within_daily_limit(self, mock_get_redis, mock_config):
        """AC1: check() retorna allowed=True quando dentro do limite diário."""
        mock_config.get = AsyncMock(return_value={"daily": 10, "burst": 2})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 1 (allowed)
        redis.eval = AsyncMock(return_value=1)

        # Daily: 3rd request (within limit of 10)
        redis.pipeline = MagicMock(return_value=_mock_pipeline(3))

        result = await RateLimiter.check("user-1", "free")

        assert result.allowed is True
        assert result.remaining_daily == 7
        assert result.daily_limit == 10
        assert result.reason == ""

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_blocked_when_daily_exceeded(self, mock_get_redis, mock_config):
        """AC1: check() retorna allowed=False quando limite diário excedido."""
        mock_config.get = AsyncMock(return_value={"daily": 10, "burst": 2})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 1 (allowed)
        redis.eval = AsyncMock(return_value=1)

        # Daily: 11th request (over limit of 10)
        redis.pipeline = MagicMock(return_value=_mock_pipeline(11))

        result = await RateLimiter.check("user-1", "free")

        assert result.allowed is False
        assert result.remaining_daily == 0
        assert result.reason == "daily_exceeded"

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_remaining_daily_correct(self, mock_get_redis, mock_config):
        """AC1: check() retorna remaining correto."""
        mock_config.get = AsyncMock(return_value={"daily": 100, "burst": 5})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 1 (allowed)
        redis.eval = AsyncMock(return_value=1)

        # 42nd request of 100
        redis.pipeline = MagicMock(return_value=_mock_pipeline(42))

        result = await RateLimiter.check("user-1", "basic")

        assert result.remaining_daily == 58
        assert result.daily_limit == 100

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_blocked_when_burst_exceeded(self, mock_get_redis, mock_config):
        """AC4: check() retorna allowed=False quando burst excedido."""
        mock_config.get = AsyncMock(return_value={"daily": 10, "burst": 2})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 0 (denied)
        redis.eval = AsyncMock(return_value=0)

        result = await RateLimiter.check("user-1", "free")

        assert result.allowed is False
        assert result.reason == "burst_exceeded"

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_burst_checked_before_sliding_window(self, mock_get_redis, mock_config):
        """AC4: burst check executado antes de sliding window."""
        mock_config.get = AsyncMock(return_value={"daily": 10, "burst": 2})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 0 (denied) → should return immediately
        redis.eval = AsyncMock(return_value=0)

        result = await RateLimiter.check("user-1", "free")

        assert result.allowed is False
        assert result.reason == "burst_exceeded"
        # Pipeline should NOT have been called (burst fails before daily check)
        redis.pipeline.assert_not_called()

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_loads_limits_from_config_service(self, mock_get_redis, mock_config):
        """AC1: limites carregados do ConfigService por tier."""
        mock_config.get = AsyncMock(return_value={"daily": 1000, "burst": 10})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 1 (allowed)
        redis.eval = AsyncMock(return_value=1)
        redis.pipeline = MagicMock(return_value=_mock_pipeline(1))

        result = await RateLimiter.check("user-1", "premium")

        mock_config.get.assert_awaited_once_with("rate_limit:premium")
        assert result.daily_limit == 1000
        assert result.remaining_daily == 999

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_redis_failure_fail_open(self, mock_get_redis, mock_config):
        """Fallback: Redis failure → fail open (allowed=True)."""
        mock_config.get = AsyncMock(return_value={"daily": 10, "burst": 2})
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Redis raises on eval (Lua script)
        redis.eval = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await RateLimiter.check("user-1", "free")

        assert result.allowed is True
        assert result.daily_limit == 10

    @patch("workflows.services.rate_limiter.ConfigService")
    @patch("workflows.services.rate_limiter._get_redis_client")
    async def test_config_failure_uses_fallback_limits(self, mock_get_redis, mock_config):
        """Fallback: ConfigService failure → hardcoded fallback limits."""
        mock_config.get = AsyncMock(side_effect=Exception("DB down"))
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        # Burst: Lua script returns 1 (allowed)
        redis.eval = AsyncMock(return_value=1)
        redis.pipeline = MagicMock(return_value=_mock_pipeline(1))

        result = await RateLimiter.check("user-1", "free")

        assert result.allowed is True
        assert result.daily_limit == 10  # fallback free daily limit
