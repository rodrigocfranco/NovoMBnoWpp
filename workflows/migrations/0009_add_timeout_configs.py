"""Data migration to add configurable timeout settings per external service (Story 5.1).

Creates timeout config entries for each external service integration:
- timeout:pinecone (8s) — RAG knowledge base
- timeout:whisper (20s) — Audio transcription
- timeout:tavily (10s) — Web search
- timeout:pubmed (5s) — Paper verification
- timeout:whatsapp (10s) — WhatsApp Cloud API
- timeout:bulas_med (45s) — Drug lookup global timeout
"""

from django.db import migrations

TIMEOUT_CONFIGS = [
    {"key": "timeout:pinecone", "value": 8, "updated_by": "system"},
    {"key": "timeout:whisper", "value": 20, "updated_by": "system"},
    {"key": "timeout:tavily", "value": 10, "updated_by": "system"},
    {"key": "timeout:pubmed", "value": 5, "updated_by": "system"},
    {"key": "timeout:whatsapp", "value": 10, "updated_by": "system"},
    {"key": "timeout:bulas_med", "value": 45, "updated_by": "system"},
]


def forward(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    for config_data in TIMEOUT_CONFIGS:
        Config.objects.create(**config_data)


def reverse(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    keys = [c["key"] for c in TIMEOUT_CONFIGS]
    Config.objects.filter(key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0008_add_error_fallback_config"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
