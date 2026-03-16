"""Tests for debounce service (AC1, AC2)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from workflows.services.debounce import (
    BUFFER_KEY_PREFIX,
    DEFAULT_DEBOUNCE_TTL,
    TIMER_KEY_PREFIX,
    buffer_message,
    get_and_clear_buffer,
    schedule_processing,
)


def _make_mock_redis():
    """Create a mock Redis client with pipeline support.

    redis-py's pipeline() is synchronous and returns an async context manager.
    Pipeline queueing methods (rpush, expire, incr, etc.) are synchronous;
    only execute() is async.
    """
    mock_redis = AsyncMock()
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    # Pipeline queueing methods are synchronous in redis-py
    mock_pipe.rpush = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    return mock_redis, mock_pipe


class TestBufferMessage:
    """Tests for buffer_message function."""

    @patch("workflows.services.debounce._get_redis_client")
    async def test_rpush_and_expire_called_atomically(self, mock_get_redis):
        """AC1: buffer_message faz RPUSH + EXPIRE via pipeline atômico."""
        mock_redis, mock_pipe = _make_mock_redis()
        mock_get_redis.return_value = mock_redis

        await buffer_message("5511999999999", '{"body": "hello"}', 3)

        mock_redis.pipeline.assert_called_once_with(transaction=True)
        mock_pipe.rpush.assert_called_once_with(
            f"{BUFFER_KEY_PREFIX}:5511999999999", '{"body": "hello"}'
        )
        mock_pipe.expire.assert_called_once_with(
            f"{BUFFER_KEY_PREFIX}:5511999999999",
            8,  # ttl + 5 safety margin
        )
        mock_pipe.execute.assert_awaited_once()


class TestGetAndClearBuffer:
    """Tests for get_and_clear_buffer function."""

    @patch("workflows.services.debounce._get_redis_client")
    async def test_atomic_lrange_and_delete_via_lua(self, mock_get_redis):
        """AC1: get_and_clear_buffer usa Lua script atômico (LRANGE + DELETE)."""
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = ['{"body": "msg1"}', '{"body": "msg2"}']
        mock_get_redis.return_value = mock_redis

        result = await get_and_clear_buffer("5511999999999")

        mock_redis.eval.assert_awaited_once()
        call_args = mock_redis.eval.call_args
        assert call_args[0][1] == 1  # numkeys
        assert call_args[0][2] == f"{BUFFER_KEY_PREFIX}:5511999999999"
        assert result == ['{"body": "msg1"}', '{"body": "msg2"}']

    @patch("workflows.services.debounce._get_redis_client")
    async def test_empty_buffer_returns_empty_list(self, mock_get_redis):
        """get_and_clear_buffer retorna lista vazia quando buffer não existe."""
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = None
        mock_get_redis.return_value = mock_redis

        result = await get_and_clear_buffer("5511999999999")

        assert result == []


class TestScheduleProcessing:
    """Tests for schedule_processing function."""

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_single_message_processed_after_debounce(
        self, mock_config, mock_get_redis, mock_sleep
    ):
        """AC2: Mensagem única processada após debounce_ttl."""
        mock_config.get = AsyncMock(return_value=3)

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.eval = AsyncMock(
            return_value=[json.dumps({"body": "hello", "phone": "5511999999999"})]
        )
        mock_get_redis.return_value = mock_redis

        # Make GET return our timestamp (we are the latest)
        async def get_side_effect(key):
            if key.startswith(TIMER_KEY_PREFIX):
                # Return the value that was SET
                return mock_redis.set.call_args[0][1]
            return None

        mock_redis.get.side_effect = get_side_effect

        callback = AsyncMock()
        validated = {"body": "hello", "phone": "5511999999999"}

        await schedule_processing("5511999999999", validated, callback)

        mock_sleep.assert_awaited_once_with(3)
        callback.assert_awaited_once()
        call_data = callback.call_args[0][0]
        assert call_data["body"] == "hello"

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_multiple_messages_combined(self, mock_config, mock_get_redis, mock_sleep):
        """AC1: 3 mensagens rápidas combinadas em uma única entrada."""
        mock_config.get = AsyncMock(return_value=3)

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.eval = AsyncMock(
            return_value=[
                json.dumps({"body": "parte 1", "message_type": "text"}),
                json.dumps({"body": "parte 2", "message_type": "text"}),
                json.dumps({"body": "parte 3", "message_type": "text"}),
            ]
        )
        mock_get_redis.return_value = mock_redis

        async def get_side_effect(key):
            if key.startswith(TIMER_KEY_PREFIX):
                return mock_redis.set.call_args[0][1]
            return None

        mock_redis.get.side_effect = get_side_effect

        callback = AsyncMock()
        validated = {"body": "parte 1", "message_type": "text"}

        await schedule_processing("5511999999999", validated, callback)

        callback.assert_awaited_once()
        call_data = callback.call_args[0][0]
        assert call_data["body"] == "parte 1\nparte 2\nparte 3"

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_last_message_wins_timer_superseded(
        self, mock_config, mock_get_redis, mock_sleep
    ):
        """AC1: Timer antigo não processa — last-message-wins."""
        mock_config.get = AsyncMock(return_value=3)

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value="different_timestamp")
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        callback = AsyncMock()
        validated = {"body": "old", "message_type": "text"}

        await schedule_processing("5511999999999", validated, callback)

        mock_sleep.assert_awaited_once_with(3)
        callback.assert_not_awaited()

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_debounce_ttl_loaded_from_config(self, mock_config, mock_get_redis, mock_sleep):
        """AC1: debounce_ttl carregado do ConfigService."""
        mock_config.get = AsyncMock(return_value=5)

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value="different_timestamp")
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        callback = AsyncMock()
        validated = {"body": "test", "message_type": "text"}

        await schedule_processing("5511999999999", validated, callback)

        mock_config.get.assert_awaited_once_with("debounce_ttl")
        mock_sleep.assert_awaited_once_with(5)
        # Pipeline expire uses ttl + 5
        mock_pipe.expire.assert_called_once_with(
            f"{BUFFER_KEY_PREFIX}:5511999999999",
            10,  # 5 + 5
        )

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_config_failure_uses_default_ttl(self, mock_config, mock_get_redis, mock_sleep):
        """AC1: ConfigService falha → usa DEFAULT_DEBOUNCE_TTL (3)."""
        mock_config.get = AsyncMock(side_effect=Exception("Config unavailable"))

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value="different_timestamp")
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        callback = AsyncMock()
        validated = {"body": "test", "message_type": "text"}

        await schedule_processing("5511999999999", validated, callback)

        mock_sleep.assert_awaited_once_with(DEFAULT_DEBOUNCE_TTL)

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_empty_buffer_after_timer_wins_skips_callback(
        self, mock_config, mock_get_redis, mock_sleep
    ):
        """Buffer vazio após timer vencer → callback NÃO é chamado."""
        mock_config.get = AsyncMock(return_value=3)

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.eval = AsyncMock(return_value=None)  # Empty buffer
        mock_get_redis.return_value = mock_redis

        async def get_side_effect(key):
            if key.startswith(TIMER_KEY_PREFIX):
                return mock_redis.set.call_args[0][1]
            return None

        mock_redis.get.side_effect = get_side_effect

        callback = AsyncMock()
        validated = {"body": "test", "message_type": "text"}

        await schedule_processing("5511999999999", validated, callback)

        callback.assert_not_awaited()

    @patch("workflows.services.debounce.asyncio.sleep", new_callable=AsyncMock)
    @patch("workflows.services.debounce._get_redis_client")
    @patch("workflows.services.debounce.ConfigService")
    async def test_corrupted_json_in_buffer_skipped_gracefully(
        self, mock_config, mock_get_redis, mock_sleep
    ):
        """Entrada JSON corrompida no buffer é ignorada sem perder o batch."""
        mock_config.get = AsyncMock(return_value=3)

        mock_redis, mock_pipe = _make_mock_redis()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.eval = AsyncMock(
            return_value=[
                json.dumps({"body": "msg válida", "message_type": "text"}),
                "CORRUPTED_NOT_JSON",
                json.dumps({"body": "outra válida", "message_type": "text"}),
            ]
        )
        mock_get_redis.return_value = mock_redis

        async def get_side_effect(key):
            if key.startswith(TIMER_KEY_PREFIX):
                return mock_redis.set.call_args[0][1]
            return None

        mock_redis.get.side_effect = get_side_effect

        callback = AsyncMock()
        validated = {"body": "msg válida", "message_type": "text"}

        await schedule_processing("5511999999999", validated, callback)

        callback.assert_awaited_once()
        call_data = callback.call_args[0][0]
        assert call_data["body"] == "msg válida\noutra válida"
