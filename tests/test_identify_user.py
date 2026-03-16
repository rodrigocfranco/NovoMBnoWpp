"""Tests for identify_user graph node (AC1, AC2)."""

from unittest.mock import AsyncMock, patch

import pytest

from workflows.whatsapp.nodes.identify_user import identify_user


@pytest.mark.django_db(transaction=True)
class TestIdentifyUser:
    """Tests for the identify_user LangGraph node."""

    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_existing_user_returns_correct_data(self, mock_cache):
        """AC1: Usuário existente → retorna user_id e subscription_tier corretos."""
        from workflows.models import User

        user = await User.objects.acreate(phone="5511999999999", subscription_tier="premium")
        mock_cache.get_session = AsyncMock(return_value=None)
        mock_cache.cache_session = AsyncMock()

        state = {"phone_number": "5511999999999"}
        result = await identify_user(state)

        assert result["user_id"] == str(user.id)
        assert result["subscription_tier"] == "premium"
        assert result["is_new_user"] is False

    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_new_user_created_with_free_tier(self, mock_cache):
        """AC2: Usuário novo → cria com tier='free' e retorna dados."""
        from workflows.models import User

        mock_cache.get_session = AsyncMock(return_value=None)
        mock_cache.cache_session = AsyncMock()

        state = {"phone_number": "5511888888888"}
        result = await identify_user(state)

        assert result["subscription_tier"] == "free"
        assert result["user_id"]
        assert result["is_new_user"] is True

        # Verify user was persisted
        user = await User.objects.aget(phone="5511888888888")
        assert user.subscription_tier == "free"

    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_cache_hit_skips_db_query(self, mock_cache):
        """AC1: Cache hit → não consulta banco."""
        mock_cache.get_session = AsyncMock(
            return_value={"user_id": "99", "subscription_tier": "basic"}
        )

        phone = "5511777777777"
        state = {"phone_number": phone}
        result = await identify_user(state)

        assert result["user_id"] == "99"
        assert result["subscription_tier"] == "basic"
        assert result["is_new_user"] is False
        # Verify cache lookup uses the same key (phone) as cache write
        mock_cache.get_session.assert_awaited_once_with(phone)

    @patch("workflows.whatsapp.nodes.identify_user.CacheManager")
    async def test_cache_miss_queries_db_and_populates_cache(self, mock_cache):
        """AC1: Cache miss → consulta banco e popula cache com mesma chave de lookup."""
        from workflows.models import User

        phone = "5511666666666"
        user = await User.objects.acreate(phone=phone, subscription_tier="basic")
        mock_cache.get_session = AsyncMock(return_value=None)
        mock_cache.cache_session = AsyncMock()

        state = {"phone_number": phone}
        result = await identify_user(state)

        assert result["user_id"] == str(user.id)
        # Verify get and set use the SAME key (phone) for cache consistency
        mock_cache.get_session.assert_awaited_once_with(phone)
        mock_cache.cache_session.assert_awaited_once_with(
            phone,
            {"user_id": str(user.id), "subscription_tier": "basic"},
        )
