"""Integration tests for rate limiter with REAL Redis.

Validates race-condition-prone operations that mocks cannot catch:
- Token bucket Lua script atomicity
- Sliding window INCR+EXPIRE pipeline atomicity
- Concurrent request handling

Run: DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/ -m integration
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from workflows.services.rate_limiter import RateLimiter

pytestmark = pytest.mark.integration


USER_ID = "test-user-integration-001"


@pytest.mark.django_db
class TestRateLimiterReal:
    """Rate limiter with real Redis — validates Lua script + pipeline atomicity."""

    @patch("workflows.services.rate_limiter.ConfigService")
    async def test_burst_limit_enforced_via_lua(self, mock_config, redis_client):
        """Lua script token bucket bloqueia burst corretamente."""
        mock_config.get = AsyncMock(return_value={"daily": 100, "burst": 3})

        # 3 requests should pass (burst limit = 3)
        results = []
        for _ in range(3):
            r = await RateLimiter.check(USER_ID, "free")
            results.append(r.allowed)

        assert all(results), "Primeiras 3 requests devem passar"

        # 4th request should be blocked (burst exceeded)
        r4 = await RateLimiter.check(USER_ID, "free")
        assert not r4.allowed
        assert r4.reason == "burst_exceeded"

    @patch("workflows.services.rate_limiter.ConfigService")
    async def test_daily_limit_enforced_via_pipeline(
        self,
        mock_config,
        redis_client,
    ):
        """Pipeline INCR+EXPIRE bloqueia quando daily limit excedido."""
        mock_config.get = AsyncMock(return_value={"daily": 5, "burst": 100})

        # 5 requests should pass
        for i in range(5):
            r = await RateLimiter.check(USER_ID, "free")
            assert r.allowed, f"Request {i + 1} deveria passar"

        # 6th should be blocked
        r6 = await RateLimiter.check(USER_ID, "free")
        assert not r6.allowed
        assert r6.reason == "daily_exceeded"
        assert r6.remaining_daily == 0

    @patch("workflows.services.rate_limiter.ConfigService")
    async def test_remaining_count_decrements(self, mock_config, redis_client):
        """remaining_daily decrementa corretamente a cada request."""
        mock_config.get = AsyncMock(return_value={"daily": 10, "burst": 100})

        r1 = await RateLimiter.check(USER_ID, "free")
        assert r1.remaining_daily == 9

        r2 = await RateLimiter.check(USER_ID, "free")
        assert r2.remaining_daily == 8

    @patch("workflows.services.rate_limiter.ConfigService")
    async def test_concurrent_requests_no_race_condition(
        self,
        mock_config,
        redis_client,
    ):
        """Requests concorrentes não causam race condition no Lua script.

        Este é o teste que MOCKS NÃO CONSEGUEM validar — verificamos que
        o token bucket Lua script é atomicamente seguro sob concorrência.
        """
        mock_config.get = AsyncMock(return_value={"daily": 1000, "burst": 5})

        # Fire 10 concurrent requests (burst limit = 5)
        tasks = [RateLimiter.check(USER_ID, "free") for _ in range(10)]
        results = await asyncio.gather(*tasks)

        allowed = sum(1 for r in results if r.allowed)
        blocked = sum(1 for r in results if not r.allowed)

        # Exactly 5 should be allowed (burst limit)
        assert allowed == 5, (
            f"Esperava 5 permitidas, obteve {allowed} (race condition no token bucket!)"
        )
        assert blocked == 5
