"""Data migration to update rate limiting configs for Story 4.1.

Updates rate_limit:free and rate_limit:premium to daily/burst format.
Creates rate_limit:basic, rate_limit:warning_threshold,
message:rate_limit_daily, and message:rate_limit_burst.
"""

from django.db import migrations


CONFIGS_TO_CREATE = [
    {
        "key": "rate_limit:basic",
        "value": {"daily": 100, "burst": 5},
        "updated_by": "system",
    },
    {
        "key": "rate_limit:warning_threshold",
        "value": 2,
        "updated_by": "system",
    },
    {
        "key": "message:rate_limit_daily",
        "value": (
            "Você atingiu seu limite de {limit} interações por hoje. "
            "Seu limite reseta amanhã às 00h. Até lá!"
        ),
        "updated_by": "system",
    },
    {
        "key": "message:rate_limit_burst",
        "value": "Muitas mensagens em sequência. Aguarde 1 minuto.",
        "updated_by": "system",
    },
]

CONFIGS_TO_UPDATE = {
    "rate_limit:free": {"daily": 10, "burst": 2},
    "rate_limit:premium": {"daily": 1000, "burst": 10},
}

# Save old values for rollback
OLD_VALUES = {
    "rate_limit:free": {"requests_per_hour": 10, "tokens_per_day": 50000},
    "rate_limit:premium": {"requests_per_hour": 60, "tokens_per_day": 500000},
}


def forward(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")

    # Create new configs
    for config_data in CONFIGS_TO_CREATE:
        Config.objects.create(**config_data)

    # Update existing configs to new format
    for key, new_value in CONFIGS_TO_UPDATE.items():
        Config.objects.filter(key=key).update(value=new_value)


def reverse(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")

    # Remove created configs
    keys_to_remove = [c["key"] for c in CONFIGS_TO_CREATE]
    Config.objects.filter(key__in=keys_to_remove).delete()

    # Restore old values
    for key, old_value in OLD_VALUES.items():
        Config.objects.filter(key=key).update(value=old_value)


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0003_update_config_messages"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
