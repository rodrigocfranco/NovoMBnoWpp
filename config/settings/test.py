"""Test settings for mb-wpp project — uses SQLite in-memory."""

from .base import *  # noqa: F401, F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

WHATSAPP_WEBHOOK_SECRET = "test-webhook-secret"
WHATSAPP_VERIFY_TOKEN = "test-verify-token"
WHATSAPP_ACCESS_TOKEN = "test-access-token"
WHATSAPP_PHONE_NUMBER_ID = "123456789"
WHATSAPP_API_VERSION = "v21.0"

# LLM Provider (mock credentials for tests)
VERTEX_PROJECT_ID = "test-project"
VERTEX_LOCATION = "us-east5"
GCP_CREDENTIALS = ""
ANTHROPIC_API_KEY = "test-api-key"

# Tavily (mock credentials for tests)
TAVILY_API_KEY = "test-tavily-key"

# Pinecone (mock credentials for tests)
PINECONE_API_KEY = "test-pinecone-key"
PINECONE_ASSISTANT_NAME = "test-medbrain"
