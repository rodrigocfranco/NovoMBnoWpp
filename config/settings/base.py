"""Base settings for mb-wpp project."""

from pathlib import Path

import environ

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, "change-me-in-production"),
    LOG_LEVEL=(str, "INFO"),
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")

WHATSAPP_WEBHOOK_SECRET: str = env("WHATSAPP_WEBHOOK_SECRET", default="")
WHATSAPP_VERIFY_TOKEN: str = env("WHATSAPP_VERIFY_TOKEN", default="")
WHATSAPP_ACCESS_TOKEN: str = env("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID: str = env("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_API_VERSION: str = env("WHATSAPP_API_VERSION", default="v21.0")

REDIS_URL: str = env("REDIS_URL", default="redis://localhost:6379")

# GCP Vertex AI (primary LLM)
VERTEX_PROJECT_ID: str = env("VERTEX_PROJECT_ID", default="")
VERTEX_LOCATION: str = env("VERTEX_LOCATION", default="us-east5")
GCP_CREDENTIALS: str = env("GCP_CREDENTIALS", default="")

# Anthropic Direct API (fallback LLM)
ANTHROPIC_API_KEY: str = env("ANTHROPIC_API_KEY", default="")

# Tavily (Web Search)
TAVILY_API_KEY: str = env("TAVILY_API_KEY", default="")

# Pinecone (RAG via Assistant API)
PINECONE_API_KEY: str = env("PINECONE_API_KEY", default="")
PINECONE_ASSISTANT_NAME: str = env("PINECONE_ASSISTANT_NAME", default="medbrain")

# PubMed E-utilities (verificação de artigos acadêmicos)
NCBI_API_KEY: str = env("NCBI_API_KEY", default="")
NCBI_EMAIL: str = env("NCBI_EMAIL", default="")

# PharmaDB (bulas + interações medicamentosas — JWT auth)
PHARMADB_API_KEY: str = env("PHARMADB_API_KEY", default="")

# OpenAI (Whisper API — áudio transcription, Epic 3)
OPENAI_API_KEY: str | None = env("OPENAI_API_KEY", default=None)

# Langfuse (Observability — Story 7.2)
LANGFUSE_ENABLED: bool = env.bool("LANGFUSE_ENABLED", default=False)
LANGFUSE_SECRET_KEY: str = env("LANGFUSE_SECRET_KEY", default="")
LANGFUSE_PUBLIC_KEY: str = env("LANGFUSE_PUBLIC_KEY", default="")
LANGFUSE_BASE_URL: str = env("LANGFUSE_BASE_URL", default="https://cloud.langfuse.com")

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "workflows",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "workflows.middleware.webhook_signature.WebhookSignatureMiddleware",
    "workflows.middleware.trace_id.TraceIDMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgresql://postgres:postgres@localhost:5432/mb_wpp"
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL"),
    },
}
