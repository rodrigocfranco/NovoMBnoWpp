"""Fixtures for integration tests with real Redis + PostgreSQL.

Requires:
    docker compose up -d  (postgres + redis)
    DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/

Usage:
    pytest tests/integration/ -m integration
"""

import pytest
import redis.asyncio as aioredis
from django.conf import settings

_TEST_KEY_PREFIXES = (
    "msg_buffer:",
    "msg_timer:",
    "msg_processed:",
    "ratelimit:burst:",
    "ratelimit:daily:",
)


@pytest.fixture(autouse=True)
def _check_services():
    """Skip integration tests if docker-compose services aren't running."""
    import socket

    for host, port, name in [
        ("localhost", 6379, "Redis"),
        ("localhost", 5432, "PostgreSQL"),
    ]:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
        except OSError:
            pytest.skip(f"{name} not available (run: docker compose up -d)")


@pytest.fixture(autouse=True)
async def _reset_redis_singleton():
    """Reset the _get_redis_client singleton between tests.

    The production code uses a module-level singleton. Without resetting,
    a closed or broken connection from one test leaks into the next.
    """
    import workflows.utils.deduplication as dedup_mod

    original = dedup_mod._redis_client
    dedup_mod._redis_client = None
    yield
    # Close client created during test and restore
    if dedup_mod._redis_client is not None:
        await dedup_mod._redis_client.aclose()
    dedup_mod._redis_client = original


@pytest.fixture
async def redis_client():
    """Provide a real async Redis client. Cleans test keys before and after."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # Cleanup before test (in case previous test crashed)
    await _flush_test_keys(client)
    yield client
    # Cleanup after test
    await _flush_test_keys(client)
    await client.aclose()


async def _flush_test_keys(client: aioredis.Redis) -> None:
    """Delete all Redis keys matching test prefixes."""
    for prefix in _TEST_KEY_PREFIXES:
        async for key in client.scan_iter(match=f"{prefix}*"):
            await client.delete(key)
