"""Settings shared by development, tests, and production."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name, default=False):
    value = os.getenv(name, str(default)).lower()
    if value not in {"true", "false", "1", "0"}:
        raise ImproperlyConfigured(f"{name} must be true or false")
    return value in {"true", "1"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
INSTALLED_APPS = ["usage"]
MIDDLEWARE = [
    "core.middleware.RequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
APPEND_SLASH = False
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Cypienta owns the data. This gateway needs neither duplicate tables nor migrations.
DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024
CSRF_FAILURE_VIEW = "core.errors.csrf_failure"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

API_URL = os.getenv("API_URL", "").strip().rstrip("/")
API_KEY = os.getenv("API_KEY", "")

try:
    API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "10"))
    if not 0 < API_TIMEOUT_SECONDS <= 60:
        raise ValueError
except ValueError as exc:
    raise ImproperlyConfigured("API_TIMEOUT_SECONDS must be between 0 and 60") from exc

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        # HTTPX's normal INFO logs contain full URLs; only our redacted events are logged.
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}
