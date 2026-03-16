import structlog
from asgiref.sync import async_to_sync
from django.contrib import admin
from django.db import transaction
from redis.exceptions import RedisError

from workflows.models import (
    Config,
    ConfigHistory,
    CostLog,
    ErrorLog,
    Feedback,
    Message,
    SystemPromptVersion,
    ToolExecution,
    User,
)
from workflows.providers.redis import get_redis_client
from workflows.services.config_service import ConfigService

logger = structlog.get_logger(__name__)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "medway_id", "subscription_tier", "created_at")
    search_fields = ("phone", "medway_id")
    list_filter = ("subscription_tier",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "message_type", "tokens_input", "tokens_output", "created_at")
    search_fields = ("content",)
    list_filter = ("role", "message_type")
    raw_id_fields = ("user",)


class ConfigHistoryInline(admin.TabularInline):
    model = ConfigHistory
    extra = 0
    readonly_fields = ("old_value", "new_value", "changed_by", "changed_at")
    can_delete = False
    ordering = ("-changed_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_by", "updated_at")
    search_fields = ("key",)
    readonly_fields = ("updated_at", "updated_by")
    inlines = [ConfigHistoryInline]

    def save_model(self, request, obj, form, change):
        """Auto-populate updated_by, create audit trail, invalidate cache."""
        # 1. Auto-populate updated_by
        obj.updated_by = request.user.username

        # 2. Capture old_value before save (only for existing configs)
        old_value = None
        if change and obj.pk:
            try:
                old_value = Config.objects.filter(pk=obj.pk).values_list("value", flat=True).first()
            except Exception:
                logger.warning("config_old_value_capture_failed", key=obj.key)

        # 3. Save to DB
        super().save_model(request, obj, form, change)

        # 4. Create ConfigHistory
        ConfigHistory.objects.create(
            config=obj,
            old_value=old_value,
            new_value=obj.value,
            changed_by=request.user.username,
        )

        # 5. Invalidate Redis cache
        try:
            async_to_sync(ConfigService.invalidate)(obj.key)
        except Exception:
            logger.warning("config_cache_invalidation_failed", key=obj.key)


@admin.register(ConfigHistory)
class ConfigHistoryAdmin(admin.ModelAdmin):
    list_display = ("config", "old_value", "new_value", "changed_by", "changed_at")
    list_filter = ("changed_by",)
    raw_id_fields = ("config",)
    readonly_fields = ("config", "old_value", "new_value", "changed_by", "changed_at")
    ordering = ("-changed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "rating", "has_comment", "created_at")
    list_filter = ("rating",)
    date_hierarchy = "created_at"
    search_fields = ("user__phone", "comment")
    raw_id_fields = ("user", "message")

    @admin.display(boolean=True, description="Comentário?")
    def has_comment(self, obj):
        return bool(obj.comment)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("node", "error_type", "user", "trace_id", "created_at")
    list_filter = ("node", "error_type", "created_at")
    date_hierarchy = "created_at"
    search_fields = ("trace_id", "error_message")
    raw_id_fields = ("user",)
    readonly_fields = ("user", "node", "error_type", "error_message", "trace_id", "created_at")


@admin.register(CostLog)
class CostLogAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "provider",
        "model",
        "cost_usd",
        "tokens_input",
        "tokens_output",
        "created_at",
    )
    list_filter = ("provider", "model", "created_at")
    date_hierarchy = "created_at"
    raw_id_fields = ("user",)
    readonly_fields = (
        "user",
        "provider",
        "model",
        "cost_usd",
        "tokens_input",
        "tokens_output",
        "tokens_cache_creation",
        "tokens_cache_read",
        "created_at",
    )


@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = ("user", "tool_name", "latency_ms", "success", "created_at")
    list_filter = ("tool_name", "success")
    raw_id_fields = ("user",)
    readonly_fields = ("user", "tool_name", "latency_ms", "success", "error", "created_at")


PROMPT_CACHE_KEY = "config:system_prompt"


def _invalidate_prompt_cache():
    """Invalidar cache Redis do system prompt (sync context)."""

    async def _delete():
        redis = get_redis_client()
        await redis.delete(PROMPT_CACHE_KEY)

    try:
        async_to_sync(_delete)()
    except (RedisError, RuntimeError, OSError):
        logger.warning("prompt_cache_invalidation_failed")


@admin.register(SystemPromptVersion)
class SystemPromptVersionAdmin(admin.ModelAdmin):
    list_display = ("pk", "author", "is_active", "content_preview", "created_at")
    list_filter = ("is_active", "author")
    readonly_fields = ("created_at",)
    actions = ["activate_version"]
    ordering = ["-created_at"]

    @admin.display(description="Conteúdo (preview)")
    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    @admin.action(description="Ativar versão selecionada (desativa as demais)")
    def activate_version(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Selecione exatamente UMA versão.", level="error")
            return
        version = queryset.first()
        with transaction.atomic():
            SystemPromptVersion.objects.filter(is_active=True).update(is_active=False)
            version.is_active = True
            version.save(update_fields=["is_active"])
        _invalidate_prompt_cache()
        logger.info(
            "system_prompt_activated",
            version_id=version.pk,
            activated_by=request.user.username,
        )
        self.message_user(request, f"Versão {version.pk} ativada com sucesso.")

    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user.username or request.user.email or "admin"
        with transaction.atomic():
            if obj.is_active:
                SystemPromptVersion.objects.filter(is_active=True).exclude(pk=obj.pk).update(
                    is_active=False
                )
            super().save_model(request, obj, form, change)
        if obj.is_active:
            _invalidate_prompt_cache()
