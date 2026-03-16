"""Tests for load_context graph node (AC3)."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from workflows.whatsapp.nodes.load_context import load_context


@pytest.mark.django_db(transaction=True)
class TestLoadContext:
    """Tests for the load_context LangGraph node."""

    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    async def test_loads_last_20_messages_chronologically(self, mock_cache):
        """AC3: Carrega últimas 20 mensagens ordenadas cronologicamente (oldest first)."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone="5511999999999")

        # Create 25 messages — only last 20 should be loaded
        for i in range(25):
            role = "user" if i % 2 == 0 else "assistant"
            await Message.objects.acreate(
                user=user,
                content=f"Message {i}",
                role=role,
            )

        mock_cache.get_session = AsyncMock(return_value=None)
        mock_cache.cache_session = AsyncMock()

        state = {"user_id": str(user.id)}
        result = await load_context(state)

        # Should return exactly 20 messages
        assert len(result["messages"]) == 20
        # Should be in chronological order (oldest first)
        assert result["messages"][0].content == "Message 5"
        assert result["messages"][-1].content == "Message 24"

    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    async def test_formats_as_langchain_messages(self, mock_cache):
        """AC3: Formata corretamente como HumanMessage/AIMessage."""
        from workflows.models import Message, User

        user = await User.objects.acreate(phone="5511888888888")
        await Message.objects.acreate(user=user, content="Pergunta", role="user")
        await Message.objects.acreate(user=user, content="Resposta", role="assistant")

        mock_cache.get_session = AsyncMock(return_value=None)
        mock_cache.cache_session = AsyncMock()

        state = {"user_id": str(user.id)}
        result = await load_context(state)

        assert len(result["messages"]) == 2
        assert isinstance(result["messages"][0], HumanMessage)
        assert result["messages"][0].content == "Pergunta"
        assert isinstance(result["messages"][1], AIMessage)
        assert result["messages"][1].content == "Resposta"

    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    async def test_cache_hit_returns_messages_without_db_query(self, mock_cache):
        """AC3: Cache hit retorna mensagens sem query ao banco."""
        cached_messages = [
            {"type": "human", "content": "Cached question"},
            {"type": "ai", "content": "Cached answer"},
        ]
        mock_cache.get_session = AsyncMock(return_value={"messages": cached_messages})

        state = {"user_id": "99"}
        result = await load_context(state)

        assert len(result["messages"]) == 2
        assert isinstance(result["messages"][0], HumanMessage)
        assert isinstance(result["messages"][1], AIMessage)

    @patch("workflows.whatsapp.nodes.load_context.CacheManager")
    async def test_user_without_messages_returns_empty_list(self, mock_cache):
        """AC3: Usuário sem mensagens retorna lista vazia."""
        from workflows.models import User

        user = await User.objects.acreate(phone="5511777777777")
        mock_cache.get_session = AsyncMock(return_value=None)
        mock_cache.cache_session = AsyncMock()

        state = {"user_id": str(user.id)}
        result = await load_context(state)

        assert result["messages"] == []
