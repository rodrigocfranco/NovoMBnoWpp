"""Data migration to populate initial configuration values."""
from django.db import migrations


INITIAL_CONFIGS = [
    {
        "key": "rate_limit:free",
        "value": {"requests_per_hour": 10, "tokens_per_day": 50000},
        "updated_by": "system",
    },
    {
        "key": "rate_limit:premium",
        "value": {"requests_per_hour": 60, "tokens_per_day": 500000},
        "updated_by": "system",
    },
    {
        "key": "blocked_competitors",
        "value": ["chatgpt", "gemini", "copilot"],
        "updated_by": "system",
    },
    {
        "key": "message:welcome",
        "value": (
            "Olá! 👋 Sou o Medbrain, seu tutor médico da Medway. "
            "Como posso te ajudar nos estudos hoje?"
        ),
        "updated_by": "system",
    },
    {
        "key": "message:rate_limit",
        "value": (
            "Você atingiu o limite de mensagens por hora. "
            "Aguarde um pouco antes de enviar novas perguntas."
        ),
        "updated_by": "system",
    },
    {
        "key": "message:unsupported_type",
        "value": (
            "Desculpe, ainda não consigo processar esse tipo de mensagem. "
            "Por enquanto, envie mensagens de texto."
        ),
        "updated_by": "system",
    },
    {
        "key": "debounce_ttl",
        "value": 3,
        "updated_by": "system",
    },
]


def populate_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    for config_data in INITIAL_CONFIGS:
        Config.objects.create(**config_data)


def remove_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    keys = [c["key"] for c in INITIAL_CONFIGS]
    Config.objects.filter(key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(populate_configs, remove_configs),
    ]
