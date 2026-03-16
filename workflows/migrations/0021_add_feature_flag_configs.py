from django.db import migrations


def add_feature_flag_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    configs = [
        {
            "key": "feature_flag:new_pipeline",
            "value": {
                "rollout_percentage": 0,
                "description": "Roteamento gradual n8n → código novo",
            },
            "updated_by": "migration",
        },
        {
            "key": "feature_flag:shadow_mode",
            "value": {
                "rollout_percentage": 0,
                "description": "Shadow Mode para comparação de respostas",
            },
            "updated_by": "migration",
        },
    ]
    for config in configs:
        Config.objects.update_or_create(key=config["key"], defaults=config)


def remove_feature_flag_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    Config.objects.filter(key__startswith="feature_flag:").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0020_seed_system_prompt_v2_quiz"),
    ]

    operations = [
        migrations.RunPython(add_feature_flag_configs, remove_feature_flag_configs),
    ]
