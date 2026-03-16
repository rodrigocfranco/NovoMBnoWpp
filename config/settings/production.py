"""Production settings for mb-wpp project."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403
from .base import env

DEBUG = False

_secret_key = os.environ.get("SECRET_KEY", "")
if not _secret_key or _secret_key == "change-me-in-production":
    raise ImproperlyConfigured(
        "SECRET_KEY must be explicitly set in production to a secure random value."
    )
SECRET_KEY = _secret_key

_webhook_secret = os.environ.get("WHATSAPP_WEBHOOK_SECRET", "")
if not _webhook_secret:
    raise ImproperlyConfigured("WHATSAPP_WEBHOOK_SECRET must be set in production.")
WHATSAPP_WEBHOOK_SECRET = _webhook_secret

_verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
if not _verify_token:
    raise ImproperlyConfigured("WHATSAPP_VERIFY_TOKEN must be set in production.")
WHATSAPP_VERIFY_TOKEN = _verify_token

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
