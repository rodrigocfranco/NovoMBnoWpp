"""Data migration to add feedback message configs (Story 6.1).

Creates config keys for feedback prompt, thanks, comment prompt and comment thanks.
"""

from django.db import migrations


def forward(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")

    configs = [
        {
            "key": "message:feedback_prompt",
            "defaults": {
                "value": "Como você avalia esta resposta?",
                "updated_by": "migration",
            },
        },
        {
            "key": "message:feedback_thanks",
            "defaults": {
                "value": "Obrigado pelo feedback! \U0001f64f",
                "updated_by": "migration",
            },
        },
        {
            "key": "message:feedback_comment_prompt",
            "defaults": {
                "value": "Obrigado! Pode me contar o motivo da sua avaliação?",
                "updated_by": "migration",
            },
        },
        {
            "key": "message:feedback_comment_thanks",
            "defaults": {
                "value": "Obrigado pelo seu comentário! Vamos usar para melhorar. \U0001f64f",
                "updated_by": "migration",
            },
        },
    ]
    for cfg in configs:
        Config.objects.get_or_create(key=cfg["key"], defaults=cfg["defaults"])


def reverse(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(
        key__in=[
            "message:feedback_prompt",
            "message:feedback_thanks",
            "message:feedback_comment_prompt",
            "message:feedback_comment_thanks",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0010_add_feedback_model"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
