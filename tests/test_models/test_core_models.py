from decimal import Decimal

import pytest
from django.db import IntegrityError

from workflows.models import (
    Config,
    ConfigHistory,
    CostLog,
    Message,
    SystemPromptVersion,
    ToolExecution,
    User,
)


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = User.objects.create(phone="+5511999999999", subscription_tier="free")
        assert user.phone == "+5511999999999"
        assert user.subscription_tier == "free"
        assert user.medway_id is None
        assert user.metadata == {}
        assert user.created_at is not None

    def test_user_phone_unique(self):
        User.objects.create(phone="+5511999999999")
        with pytest.raises(IntegrityError):
            User.objects.create(phone="+5511999999999")

    def test_user_str(self):
        user = User.objects.create(phone="+5511888888888")
        assert str(user) == "User(+5511888888888)"

    def test_user_medway_id_nullable(self):
        user = User.objects.create(phone="+5511777777777", medway_id=None)
        assert user.medway_id is None

    def test_user_medway_id_unique(self):
        User.objects.create(phone="+5511666666666", medway_id="medway-001")
        with pytest.raises(IntegrityError):
            User.objects.create(phone="+5511555555555", medway_id="medway-001")

    def test_user_db_table(self):
        assert User._meta.db_table == "users"


@pytest.mark.django_db
class TestMessageModel:
    def test_create_message(self):
        user = User.objects.create(phone="+5511999999999")
        msg = Message.objects.create(user=user, content="Olá", role="user", message_type="text")
        assert msg.user == user
        assert msg.content == "Olá"
        assert msg.role == "user"
        assert msg.message_type == "text"
        assert msg.tokens_input is None
        assert msg.tokens_output is None
        assert msg.cost_usd is None
        assert msg.created_at is not None

    def test_message_default_type(self):
        user = User.objects.create(phone="+5511999999999")
        msg = Message.objects.create(user=user, content="test", role="assistant")
        assert msg.message_type == "text"

    def test_message_str(self):
        user = User.objects.create(phone="+5511999999999")
        msg = Message.objects.create(user=user, content="test", role="user")
        assert "user" in str(msg)

    def test_message_db_table(self):
        assert Message._meta.db_table == "messages"


@pytest.mark.django_db
class TestConfigModel:
    def test_create_config(self):
        config = Config.objects.create(key="test_key", value={"setting": True}, updated_by="system")
        assert config.key == "test_key"
        assert config.value == {"setting": True}
        assert config.updated_by == "system"
        assert config.updated_at is not None

    def test_config_key_unique(self):
        Config.objects.create(key="unique_key", value="v1", updated_by="system")
        with pytest.raises(IntegrityError):
            Config.objects.create(key="unique_key", value="v2", updated_by="system")

    def test_config_str(self):
        config = Config.objects.create(key="my_key", value=1, updated_by="system")
        assert str(config) == "Config(my_key)"

    def test_config_db_table(self):
        assert Config._meta.db_table == "configs"


@pytest.mark.django_db
class TestConfigHistoryModel:
    def test_create_config_history(self):
        config = Config.objects.create(key="ch_key", value="new", updated_by="system")
        history = ConfigHistory.objects.create(
            config=config,
            old_value="old",
            new_value="new",
            changed_by="admin",
        )
        assert history.config == config
        assert history.old_value == "old"
        assert history.new_value == "new"
        assert history.changed_by == "admin"
        assert history.changed_at is not None

    def test_config_history_db_table(self):
        assert ConfigHistory._meta.db_table == "config_history"


@pytest.mark.django_db
class TestCostLogModel:
    def test_create_costlog(self):
        user = User.objects.create(phone="+5511999990001")
        log = CostLog.objects.create(
            user=user,
            provider="vertex_ai",
            model="claude-haiku-4-5@20251001",
            tokens_input=1500,
            tokens_output=350,
            tokens_cache_creation=200,
            tokens_cache_read=1000,
            cost_usd=Decimal("0.007200"),
        )
        assert log.user == user
        assert log.provider == "vertex_ai"
        assert log.model == "claude-haiku-4-5@20251001"
        assert log.tokens_input == 1500
        assert log.tokens_output == 350
        assert log.tokens_cache_creation == 200
        assert log.tokens_cache_read == 1000
        assert log.cost_usd == Decimal("0.007200")
        assert log.created_at is not None

    def test_costlog_defaults(self):
        user = User.objects.create(phone="+5511999990002")
        log = CostLog.objects.create(
            user=user,
            provider="anthropic_direct",
            model="claude-haiku-4-5-20251001",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.000350"),
        )
        assert log.tokens_cache_creation == 0
        assert log.tokens_cache_read == 0

    def test_costlog_str(self):
        user = User.objects.create(phone="+5511999990003")
        log = CostLog.objects.create(
            user=user,
            provider="vertex_ai",
            model="claude-haiku-4-5@20251001",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.001000"),
        )
        assert f"${log.cost_usd}" in str(log)

    def test_costlog_db_table(self):
        assert CostLog._meta.db_table == "cost_logs"

    def test_costlog_indexes(self):
        index_fields = [idx.fields for idx in CostLog._meta.indexes]
        assert ["user"] in index_fields
        assert ["-created_at"] in index_fields


@pytest.mark.django_db
class TestToolExecutionModel:
    def test_create_tool_execution(self):
        user = User.objects.create(phone="+5511999990004")
        te = ToolExecution.objects.create(
            user=user,
            tool_name="drug_lookup",
            latency_ms=150,
            success=True,
        )
        assert te.user == user
        assert te.tool_name == "drug_lookup"
        assert te.latency_ms == 150
        assert te.success is True
        assert te.error is None
        assert te.created_at is not None

    def test_tool_execution_with_error(self):
        user = User.objects.create(phone="+5511999990005")
        te = ToolExecution.objects.create(
            user=user,
            tool_name="web_search",
            latency_ms=5000,
            success=False,
            error="Timeout after 10s",
        )
        assert te.success is False
        assert te.error == "Timeout after 10s"

    def test_tool_execution_nullable_latency(self):
        user = User.objects.create(phone="+5511999990006")
        te = ToolExecution.objects.create(
            user=user,
            tool_name="rag_search",
            latency_ms=None,
            success=True,
        )
        assert te.latency_ms is None

    def test_tool_execution_str(self):
        user = User.objects.create(phone="+5511999990007")
        te = ToolExecution.objects.create(
            user=user,
            tool_name="drug_lookup",
            latency_ms=100,
            success=True,
        )
        assert "drug_lookup" in str(te)
        assert "True" in str(te)

    def test_tool_execution_db_table(self):
        assert ToolExecution._meta.db_table == "tool_executions"

    def test_tool_execution_indexes(self):
        index_fields = [idx.fields for idx in ToolExecution._meta.indexes]
        assert ["tool_name"] in index_fields
        assert ["-created_at"] in index_fields


class TestAdminRegistration:
    """Tests for CostLog and ToolExecution admin registration (AC#3)."""

    def test_costlog_admin_registered(self):
        from django.contrib.admin import site

        assert CostLog in site._registry

    def test_toolexecution_admin_registered(self):
        from django.contrib.admin import site

        assert ToolExecution in site._registry

    def test_costlog_admin_config(self):
        from django.contrib.admin.sites import AdminSite

        from workflows.admin import CostLogAdmin

        admin = CostLogAdmin(CostLog, AdminSite())
        assert "user" in admin.list_display
        assert "provider" in admin.list_display
        assert "model" in admin.list_display
        assert "cost_usd" in admin.list_display
        assert "created_at" in admin.list_display
        assert admin.date_hierarchy == "created_at"
        assert "user" in admin.raw_id_fields

    def test_toolexecution_admin_config(self):
        from django.contrib.admin.sites import AdminSite

        from workflows.admin import ToolExecutionAdmin

        admin = ToolExecutionAdmin(ToolExecution, AdminSite())
        assert "user" in admin.list_display
        assert "tool_name" in admin.list_display
        assert "latency_ms" in admin.list_display
        assert "success" in admin.list_display
        assert "created_at" in admin.list_display
        assert "user" in admin.raw_id_fields


@pytest.mark.django_db
class TestSystemPromptVersionModel:
    @pytest.fixture(autouse=True)
    def _clear_seed(self):
        """Deactivate seed version so tests can control is_active."""
        SystemPromptVersion.objects.filter(is_active=True).update(is_active=False)

    def test_create_version(self):
        version = SystemPromptVersion.objects.create(
            content="Você é o Medbrain...",
            author="admin",
            is_active=True,
        )
        assert version.content == "Você é o Medbrain..."
        assert version.author == "admin"
        assert version.is_active is True
        assert version.created_at is not None
        assert version.pk is not None

    def test_str_active(self):
        version = SystemPromptVersion.objects.create(
            content="prompt", author="system", is_active=True
        )
        result = str(version)
        assert "ATIVA" in result
        assert "system" in result
        assert f"v{version.pk}" in result

    def test_str_inactive(self):
        version = SystemPromptVersion.objects.create(
            content="prompt", author="admin", is_active=False
        )
        result = str(version)
        assert "inativa" in result
        assert "admin" in result

    def test_unique_active_constraint(self):
        """AC1: Apenas UMA versão pode ter is_active=True por vez."""
        SystemPromptVersion.objects.create(content="v1", author="system", is_active=True)
        with pytest.raises(IntegrityError):
            SystemPromptVersion.objects.create(content="v2", author="admin", is_active=True)

    def test_multiple_inactive_allowed(self):
        """Múltiplas versões inativas são permitidas."""
        v1 = SystemPromptVersion.objects.create(content="v1", author="system", is_active=False)
        v2 = SystemPromptVersion.objects.create(content="v2", author="admin", is_active=False)
        assert v1.pk != v2.pk

    def test_db_table(self):
        assert SystemPromptVersion._meta.db_table == "system_prompt_versions"

    def test_ordering(self):
        assert SystemPromptVersion._meta.ordering == ["-created_at"]

    def test_default_is_active_false(self):
        version = SystemPromptVersion.objects.create(content="prompt", author="system")
        assert version.is_active is False


class TestMigrationSeedPromptIntegrity:
    """Verify data migration prompt matches hardcoded SYSTEM_PROMPT (Retro Watch Item #5)."""

    def test_initial_prompt_matches_system_prompt(self):
        """Latest migration prompt must be identical to SYSTEM_PROMPT."""
        import importlib

        migration = importlib.import_module("workflows.migrations.0020_seed_system_prompt_v2_quiz")
        from workflows.whatsapp.prompts.system import SYSTEM_PROMPT

        assert migration.PROMPT_V2_QUIZ == SYSTEM_PROMPT, (
            "PROMPT_V2_QUIZ in migration 0020 diverged from SYSTEM_PROMPT in system.py. "
            "If you changed the hardcoded prompt, update the migration too (or vice versa)."
        )
