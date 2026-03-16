"""Data migration to add error fallback message config (Story 5.2).

Creates message:error_fallback config key with the friendly error message
that is sent when the LLM fails irrecoverably.
"""

from django.db import migrations


def forward(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.get_or_create(
        key="message:error_fallback",
        defaults={
            "value": (
                "Desculpe, tive uma instabilidade técnica ao processar "
                "sua pergunta. Pode enviar novamente?"
            ),
            "updated_by": "system",
        },
    )


def reverse(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key="message:error_fallback").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0007_add_drug_updated_at"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
