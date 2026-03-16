"""Data migration to update config message texts per Story 1.6 ACs."""

from django.db import migrations


UPDATED_CONFIGS = {
    "message:welcome": (
        "Olá! Sou o Medbrain, seu tutor médico pelo WhatsApp. "
        "Pode me perguntar qualquer dúvida médica — respondo com fontes verificáveis."
    ),
    "message:unsupported_type": (
        "Desculpe, no momento só consigo processar mensagens de texto, áudio e imagem."
    ),
}

# Previous values for reversibility
PREVIOUS_CONFIGS = {
    "message:welcome": (
        "Olá! 👋 Sou o Medbrain, seu tutor médico da Medway. "
        "Como posso te ajudar nos estudos hoje?"
    ),
    "message:unsupported_type": (
        "Desculpe, ainda não consigo processar esse tipo de mensagem. "
        "Por enquanto, envie mensagens de texto."
    ),
}


def update_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    for key, value in UPDATED_CONFIGS.items():
        Config.objects.filter(key=key).update(value=value)


def revert_configs(apps, schema_editor):
    Config = apps.get_model("workflows", "Config")
    for key, value in PREVIOUS_CONFIGS.items():
        Config.objects.filter(key=key).update(value=value)


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0002_initial_configs"),
    ]

    operations = [
        migrations.RunPython(update_configs, revert_configs),
    ]
