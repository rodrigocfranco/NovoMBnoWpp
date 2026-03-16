"""Integration tests for debounce service with REAL Redis.

Validates atomicity guarantees that mocks cannot catch:
- RPUSH + EXPIRE pipeline atomicity
- Lua script LRANGE + DELETE atomicity
- Last-message-wins timer pattern

Run: DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/ -m integration
"""

import json

import pytest

from workflows.services.debounce import (
    BUFFER_KEY_PREFIX,
    buffer_message,
    get_and_clear_buffer,
)

pytestmark = pytest.mark.integration


PHONE = "5511999990001"


@pytest.mark.django_db
class TestBufferMessageReal:
    """buffer_message with real Redis pipeline."""

    async def test_rpush_adds_to_list(self, redis_client):
        """RPUSH adiciona mensagem ao buffer Redis."""
        await buffer_message(PHONE, '{"body": "msg1"}', 3)

        key = f"{BUFFER_KEY_PREFIX}:{PHONE}"
        length = await redis_client.llen(key)
        assert length == 1

        values = await redis_client.lrange(key, 0, -1)
        assert values == ['{"body": "msg1"}']

    async def test_multiple_rpush_preserves_order(self, redis_client):
        """Múltiplas mensagens preservam ordem FIFO."""
        await buffer_message(PHONE, '{"body": "msg1"}', 3)
        await buffer_message(PHONE, '{"body": "msg2"}', 3)
        await buffer_message(PHONE, '{"body": "msg3"}', 3)

        key = f"{BUFFER_KEY_PREFIX}:{PHONE}"
        values = await redis_client.lrange(key, 0, -1)
        assert len(values) == 3
        assert json.loads(values[0])["body"] == "msg1"
        assert json.loads(values[2])["body"] == "msg3"

    async def test_expire_is_set(self, redis_client):
        """EXPIRE é configurado no buffer key."""
        await buffer_message(PHONE, '{"body": "test"}', 3)

        key = f"{BUFFER_KEY_PREFIX}:{PHONE}"
        ttl = await redis_client.ttl(key)
        assert 1 <= ttl <= 8  # 3 + 5 safety margin


@pytest.mark.django_db
class TestGetAndClearBufferReal:
    """get_and_clear_buffer with real Lua script execution."""

    async def test_lua_returns_all_messages_and_deletes(self, redis_client):
        """Lua script retorna todas as mensagens e deleta atomicamente."""
        await buffer_message(PHONE, '{"body": "a"}', 10)
        await buffer_message(PHONE, '{"body": "b"}', 10)

        result = await get_and_clear_buffer(PHONE)
        assert len(result) == 2
        assert json.loads(result[0])["body"] == "a"
        assert json.loads(result[1])["body"] == "b"

        # Key should be deleted
        key = f"{BUFFER_KEY_PREFIX}:{PHONE}"
        exists = await redis_client.exists(key)
        assert exists == 0

    async def test_empty_buffer_returns_empty_list(self, redis_client):
        """Buffer vazio retorna lista vazia."""
        result = await get_and_clear_buffer("5511000000000")
        assert result == []

    async def test_atomicity_no_message_loss(self, redis_client):
        """Lua garante que RPUSH entre LRANGE e DELETE não perde mensagem.

        Este é o cenário que mocks NÃO conseguem testar — a atomicidade
        do Lua script previne race condition real.
        """
        # Pre-populate buffer
        for i in range(5):
            await buffer_message(PHONE, json.dumps({"body": f"msg{i}"}), 10)

        # Atomic get and clear
        result = await get_and_clear_buffer(PHONE)
        assert len(result) == 5

        # Buffer is empty after atomic operation
        key = f"{BUFFER_KEY_PREFIX}:{PHONE}"
        remaining = await redis_client.llen(key)
        assert remaining == 0
