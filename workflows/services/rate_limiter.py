"""Dual rate limiting service: sliding window (daily) + token bucket (anti-burst)."""

from dataclasses import dataclass

import structlog

from workflows.services.config_service import ConfigService
from workflows.utils.deduplication import _get_redis_client

logger = structlog.get_logger(__name__)

# Fallback limits when ConfigService is unavailable
_FALLBACK_LIMITS = {
    "free": {"daily": 10, "burst": 2},
    "basic": {"daily": 100, "burst": 5},
    "premium": {"daily": 1000, "burst": 10},
}
_DEFAULT_FALLBACK = {"daily": 10, "burst": 2}

DAILY_TTL_SECONDS = 86400  # 24h
BURST_TTL_SECONDS = 60  # 1 min

# Lua script for atomic token bucket check (prevents race condition on GET+SET/DECR)
_BURST_CHECK_SCRIPT = """
local tokens = redis.call('GET', KEYS[1])
if tokens == false then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    return 1
end
if tonumber(tokens) <= 0 then
    return 0
end
redis.call('DECR', KEYS[1])
return 1
"""


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining_daily: int
    daily_limit: int
    reason: str  # "" if allowed, "daily_exceeded" or "burst_exceeded"


class RateLimiter:
    """Dual rate limiter: token bucket (anti-burst) + sliding window (daily)."""

    @staticmethod
    async def check(user_id: str, tier: str) -> RateLimitResult:
        """Check rate limit: burst first (fail fast), then daily sliding window.

        Args:
            user_id: Unique user identifier.
            tier: Subscription tier (free, basic, premium).

        Returns:
            RateLimitResult with allowed status and remaining counts.
        """
        redis = _get_redis_client()

        # Load tier limits from Config
        try:
            config = await ConfigService.get(f"rate_limit:{tier}")
            if isinstance(config, dict):
                daily_limit = config["daily"]
                burst_limit = config["burst"]
            else:
                fallback = _FALLBACK_LIMITS.get(tier, _DEFAULT_FALLBACK)
                daily_limit = fallback["daily"]
                burst_limit = fallback["burst"]
        except Exception:
            logger.warning("rate_limit_config_fallback", tier=tier)
            fallback = _FALLBACK_LIMITS.get(tier, _DEFAULT_FALLBACK)
            daily_limit = fallback["daily"]
            burst_limit = fallback["burst"]

        try:
            # 1. Burst check FIRST (cheaper, fail fast) — atomic via Lua script
            burst_key = f"ratelimit:burst:{user_id}"
            burst_allowed = await redis.eval(
                _BURST_CHECK_SCRIPT,
                1,
                burst_key,
                str(burst_limit - 1),
                str(BURST_TTL_SECONDS),
            )
            if not burst_allowed:
                logger.info("burst_limit_exceeded", user_id=user_id, tier=tier)
                return RateLimitResult(
                    allowed=False,
                    remaining_daily=0,
                    daily_limit=daily_limit,
                    reason="burst_exceeded",
                )

            # 2. Sliding window (daily limit) — atomic INCR + EXPIRE via pipeline
            daily_key = f"ratelimit:daily:{user_id}"
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(daily_key)
                pipe.expire(daily_key, DAILY_TTL_SECONDS)
                results = await pipe.execute()
                daily_count = results[0]

            remaining = max(0, daily_limit - daily_count)

            if daily_count > daily_limit:
                logger.info(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    tier=tier,
                    daily_count=daily_count,
                    daily_limit=daily_limit,
                )
                return RateLimitResult(
                    allowed=False,
                    remaining_daily=0,
                    daily_limit=daily_limit,
                    reason="daily_exceeded",
                )

            logger.debug(
                "rate_limit_checked",
                user_id=user_id,
                tier=tier,
                remaining=remaining,
            )
            return RateLimitResult(
                allowed=True,
                remaining_daily=remaining,
                daily_limit=daily_limit,
                reason="",
            )

        except Exception:
            # Fail open — if Redis is down, allow the message
            logger.exception("rate_limit_redis_error", user_id=user_id)
            return RateLimitResult(
                allowed=True,
                remaining_daily=daily_limit,
                daily_limit=daily_limit,
                reason="",
            )
