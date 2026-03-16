from django.db import migrations


def create_alert_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    configs = [
        {"key": "alert:cost_daily_threshold", "value": 50.0, "updated_by": "migration"},
        {"key": "alert:error_rate_threshold", "value": 5.0, "updated_by": "migration"},
    ]
    for cfg in configs:
        Config.objects.get_or_create(key=cfg["key"], defaults=cfg)


def remove_alert_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key__startswith="alert:").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0018_add_errorlog"),
    ]

    operations = [
        migrations.RunPython(create_alert_configs, remove_alert_configs),
    ]
