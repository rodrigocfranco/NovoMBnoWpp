"""Development settings for mb-wpp project."""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

# Uses DATABASE_URL from .env (base.py already parses it)
# PostgreSQL required for LangGraph checkpointer
