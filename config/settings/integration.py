"""Integration test settings — uses real PostgreSQL + Redis from docker-compose."""

from .base import *  # noqa: F401, F403

DEBUG = True

# Real PostgreSQL from docker-compose (default matches docker-compose.yml)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "mb_wpp",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# Real Redis from docker-compose
REDIS_URL = "redis://localhost:6379"

# WhatsApp (mock credentials — not needed for integration tests)
WHATSAPP_WEBHOOK_SECRET = "test-webhook-secret"
WHATSAPP_VERIFY_TOKEN = "test-verify-token"
WHATSAPP_ACCESS_TOKEN = "test-access-token"
WHATSAPP_PHONE_NUMBER_ID = "123456789"
WHATSAPP_API_VERSION = "v21.0"
