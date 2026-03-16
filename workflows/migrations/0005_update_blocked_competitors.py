"""Data migration to update blocked_competitors with correct competitor domains.

The initial migration (0002) had incorrect values (chatgpt, gemini, copilot).
This migration corrects them to actual competitor domains for web search filtering.
"""

from django.db import migrations

NEW_VALUE = {
    "domains": [
        "medgrupo.com.br",
        "grupomedcof.com.br",
        "med.estrategia.com",
        "estrategia.com",
        "medcel.com.br",
        "sanarmed.com",
        "sanarflix.com.br",
        "sanar.com.br",
        "aristo.com.br",
        "eumedicoresidente.com.br",
        "revisamed.com.br",
        "medprovas.com.br",
        "vrmed.com.br",
        "medmentoria.com",
        "oresidente.org",
        "afya.com.br",
    ],
    "names": [
        "medcurso",
        "medgrupo",
        "medcof",
        "estratégia med",
        "medcel",
        "afya",
        "sanar",
        "sanarflix",
        "aristo",
        "jj medicina",
        "eu médico residente",
        "revisamed",
        "mediccurso",
        "medprovas",
        "vr med",
        "medmentoria",
        "o residente",
        "yellowbook",
    ],
}

OLD_VALUE = ["chatgpt", "gemini", "copilot"]


def forward(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key="blocked_competitors").update(
        value=NEW_VALUE,
        updated_by="migration",
    )


def reverse(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key="blocked_competitors").update(
        value=OLD_VALUE,
        updated_by="system",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0004_rate_limit_configs"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
