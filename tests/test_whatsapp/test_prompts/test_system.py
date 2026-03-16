"""Tests for get_system_prompt_async() and build_system_message() (AC: #4)."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import SystemMessage
from redis.exceptions import RedisError

from workflows.whatsapp.prompts.system import SYSTEM_PROMPT


class TestGetSystemPromptAsync:
    """Tests for get_system_prompt_async() cache-aside pattern."""

    @patch("workflows.whatsapp.prompts.system.get_redis_client")
    async def test_cache_hit_returns_cached_value(self, mock_get_redis):
        """AC4: Cache hit retorna valor do Redis."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "Prompt do cache"
        mock_get_redis.return_value = mock_redis

        from workflows.whatsapp.prompts.system import get_system_prompt_async

        result = await get_system_prompt_async()

        assert result == "Prompt do cache"
        mock_redis.get.assert_called_once_with("config:system_prompt")

    @pytest.mark.django_db(transaction=True)
    @patch("workflows.whatsapp.prompts.system.get_redis_client")
    async def test_cache_miss_loads_from_db(self, mock_get_redis):
        """AC4: Cache miss busca no DB e popula cache."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss
        mock_get_redis.return_value = mock_redis

        from workflows.models import SystemPromptVersion

        # Deactivate seed and create test version
        await SystemPromptVersion.objects.filter(is_active=True).aupdate(is_active=False)
        await SystemPromptVersion.objects.acreate(
            content="Prompt do DB", author="admin", is_active=True
        )

        from workflows.whatsapp.prompts.system import get_system_prompt_async

        result = await get_system_prompt_async()

        assert result == "Prompt do DB"
        # Verify cache was populated
        mock_redis.setex.assert_called_once_with("config:system_prompt", 300, "Prompt do DB")

    @pytest.mark.django_db(transaction=True)
    @patch("workflows.whatsapp.prompts.system.get_redis_client")
    async def test_no_active_version_returns_hardcoded(self, mock_get_redis):
        """AC4: Nenhuma versão ativa no DB retorna fallback hardcoded."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss
        mock_get_redis.return_value = mock_redis

        from workflows.models import SystemPromptVersion

        # Deactivate all versions — no active version in DB
        await SystemPromptVersion.objects.filter(is_active=True).aupdate(is_active=False)

        from workflows.whatsapp.prompts.system import get_system_prompt_async

        result = await get_system_prompt_async()

        assert result == SYSTEM_PROMPT

    @pytest.mark.django_db(transaction=True)
    @patch("workflows.whatsapp.prompts.system.get_redis_client")
    async def test_redis_error_falls_back_to_db(self, mock_get_redis):
        """AC4: Redis error (cache) → fallback to DB."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Connection refused")
        mock_get_redis.return_value = mock_redis

        from workflows.models import SystemPromptVersion

        # Ensure a known active version exists
        await SystemPromptVersion.objects.filter(is_active=True).aupdate(is_active=False)
        await SystemPromptVersion.objects.acreate(
            content="Prompt do DB fallback", author="admin", is_active=True
        )

        from workflows.whatsapp.prompts.system import get_system_prompt_async

        result = await get_system_prompt_async()

        assert result == "Prompt do DB fallback"

    @pytest.mark.django_db(transaction=True)
    @patch("workflows.whatsapp.prompts.system.get_redis_client")
    async def test_redis_error_on_cache_set_does_not_break(self, mock_get_redis):
        """AC4: Redis error ao popular cache não impede retorno do DB."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss
        mock_redis.setex.side_effect = RedisError("Write failed")
        mock_get_redis.return_value = mock_redis

        from workflows.models import SystemPromptVersion

        # Ensure a known active version exists
        await SystemPromptVersion.objects.filter(is_active=True).aupdate(is_active=False)
        await SystemPromptVersion.objects.acreate(
            content="Prompt funciona", author="admin", is_active=True
        )

        from workflows.whatsapp.prompts.system import get_system_prompt_async

        result = await get_system_prompt_async()

        assert result == "Prompt funciona"

    @patch("workflows.whatsapp.prompts.system.get_redis_client")
    async def test_full_fallback_to_hardcoded(self, mock_get_redis):
        """AC4: Redis error + DB error → fallback hardcoded (zero downtime)."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Down")
        mock_get_redis.return_value = mock_redis

        # DB mock is legitimate here — simulating DB completely down
        with patch("workflows.models.SystemPromptVersion.objects") as mock_objects:
            mock_objects.filter.side_effect = Exception("DB down")

            from workflows.whatsapp.prompts.system import get_system_prompt_async

            result = await get_system_prompt_async()

        assert result == SYSTEM_PROMPT


class TestBuildSystemMessage:
    """Tests for build_system_message() async."""

    @patch("workflows.whatsapp.prompts.system.get_system_prompt_async")
    async def test_returns_system_message_with_cache_control(self, mock_get_prompt):
        """AC4: build_system_message retorna SystemMessage com cache_control."""
        mock_get_prompt.return_value = "Test prompt content"

        from workflows.whatsapp.prompts.system import build_system_message

        result = await build_system_message()

        assert isinstance(result, SystemMessage)
        content_block = result.content[0]
        assert content_block["type"] == "text"
        assert content_block["text"] == "Test prompt content"
        assert content_block["cache_control"] == {"type": "ephemeral"}

    @patch("workflows.whatsapp.prompts.system.get_system_prompt_async")
    async def test_calls_get_system_prompt_async(self, mock_get_prompt):
        """AC4: build_system_message chama get_system_prompt_async."""
        mock_get_prompt.return_value = "any prompt"

        from workflows.whatsapp.prompts.system import build_system_message

        await build_system_message()

        mock_get_prompt.assert_called_once()


class TestGetSystemPromptSync:
    """Tests for sync backward-compat wrapper."""

    def test_returns_hardcoded_prompt(self):
        from workflows.whatsapp.prompts.system import get_system_prompt

        result = get_system_prompt()
        assert result == SYSTEM_PROMPT
        assert "Medbrain" in result
