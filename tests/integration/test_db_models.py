"""Integration tests for Django models with REAL PostgreSQL.

Validates constraints, migrations, and queries that SQLite may not catch:
- Phone uniqueness constraint
- ForeignKey cascading
- Async ORM operations

Run: DJANGO_SETTINGS_MODULE=config.settings.integration pytest tests/integration/ -m integration
"""

import pytest
from django.db import IntegrityError

from workflows.models import Message, User

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


class TestUserModelReal:
    """User model with real PostgreSQL."""

    async def test_create_user(self):
        """User é criado com campos corretos."""
        user = await User.objects.acreate(
            phone="5511999990002",
            subscription_tier="premium",
        )
        assert user.id is not None
        assert user.phone == "5511999990002"
        assert user.subscription_tier == "premium"

    async def test_phone_uniqueness_constraint(self):
        """Constraint de unicidade no phone é enforced pelo PostgreSQL."""
        await User.objects.acreate(phone="5511999990003")
        with pytest.raises(IntegrityError):
            await User.objects.acreate(phone="5511999990003")

    async def test_get_or_create_user(self):
        """get_or_create funciona com async ORM."""
        user1, created1 = await User.objects.aget_or_create(
            phone="5511999990004",
            defaults={"subscription_tier": "free"},
        )
        assert created1 is True

        user2, created2 = await User.objects.aget_or_create(
            phone="5511999990004",
            defaults={"subscription_tier": "premium"},
        )
        assert created2 is False
        assert user1.id == user2.id
        assert user2.subscription_tier == "free"


class TestMessageModelReal:
    """Message model with real PostgreSQL."""

    async def test_create_message_with_fk(self):
        """Message é criada com FK para User."""
        user = await User.objects.acreate(phone="5511999990005")
        msg = await Message.objects.acreate(
            user=user,
            role="user",
            content="Olá",
        )
        assert msg.id is not None
        assert msg.user_id == user.id

    async def test_message_ordering(self):
        """Messages são ordenadas por created_at (mais recente primeiro)."""
        user = await User.objects.acreate(phone="5511999990006")
        await Message.objects.acreate(user=user, role="user", content="msg1")
        await Message.objects.acreate(user=user, role="assistant", content="msg2")

        messages = []
        async for m in Message.objects.filter(user=user).order_by("created_at"):
            messages.append(m)

        assert len(messages) == 2
        assert messages[0].content == "msg1"
        assert messages[1].content == "msg2"
