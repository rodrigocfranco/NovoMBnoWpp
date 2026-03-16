from django.db import models


class User(models.Model):
    phone = models.CharField(max_length=20, unique=True)
    medway_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    subscription_tier = models.CharField(
        max_length=10,
        choices=[
            ("free", "Free"),
            ("basic", "Basic"),
            ("premium", "Premium"),
        ],
        default="free",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return f"User({self.phone})"


class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    content = models.TextField()
    role = models.CharField(max_length=20)
    message_type = models.CharField(max_length=20, default="text")
    tokens_input = models.IntegerField(null=True, blank=True)
    tokens_output = models.IntegerField(null=True, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Message({self.role}, user={self.user_id})"


class Config(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    updated_by = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "configs"

    def __str__(self) -> str:
        return f"Config({self.key})"


class Drug(models.Model):
    generic_name = models.CharField(max_length=200)
    brand_names = models.CharField(max_length=500, blank=True, default="")
    therapeutic_class = models.CharField(max_length=200, blank=True, default="")
    indications = models.TextField(blank=True, default="")
    dosage = models.TextField(blank=True, default="")
    contraindications = models.TextField(blank=True, default="")
    interactions = models.TextField(blank=True, default="")
    adverse_effects = models.TextField(blank=True, default="")
    mechanism = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drugs"
        indexes = [
            models.Index(fields=["generic_name"]),
        ]

    def __str__(self) -> str:
        return f"Drug({self.generic_name})"


class Feedback(models.Model):
    """Feedback do aluno sobre respostas do assistente."""

    RATING_CHOICES = [
        ("positive", "Positivo"),
        ("negative", "Negativo"),
        ("comment", "Comentário"),
    ]

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="feedbacks")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    rating = models.CharField(max_length=10, choices=RATING_CHOICES)
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedbacks"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["rating"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "message"],
                name="unique_feedback_per_message",
            ),
        ]

    def __str__(self) -> str:
        return f"Feedback({self.rating}, user={self.user_id})"


class ConfigHistory(models.Model):
    config = models.ForeignKey(Config, on_delete=models.CASCADE, related_name="history")
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField()
    changed_by = models.CharField(max_length=100)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "config_history"

    def __str__(self) -> str:
        return f"ConfigHistory({self.config_id}, {self.changed_at})"


class CostLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cost_logs")
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=100)
    tokens_input = models.IntegerField()
    tokens_output = models.IntegerField()
    tokens_cache_creation = models.IntegerField(default=0)
    tokens_cache_read = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cost_logs"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"CostLog(user={self.user_id}, ${self.cost_usd})"


class SystemPromptVersion(models.Model):
    """Versioned system prompt with activation control (FR34-FR36)."""

    content = models.TextField()
    author = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_prompt_versions"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=["is_active"],
                name="unique_active_system_prompt",
            ),
        ]

    def __str__(self) -> str:
        status = "ATIVA" if self.is_active else "inativa"
        return f"SystemPromptVersion(v{self.pk}, {status}, {self.author})"


class ErrorLog(models.Model):
    """Registro de erros do pipeline para métricas queryable via Django Admin."""

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="error_logs"
    )
    node = models.CharField(max_length=100)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    trace_id = models.CharField(max_length=36, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "error_logs"
        indexes = [
            models.Index(fields=["node"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ErrorLog({self.node}, {self.error_type})"


class ToolExecution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tool_executions")
    tool_name = models.CharField(max_length=100)
    latency_ms = models.IntegerField(null=True)
    success = models.BooleanField()
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tool_executions"
        indexes = [
            models.Index(fields=["tool_name"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ToolExecution({self.tool_name}, success={self.success})"
