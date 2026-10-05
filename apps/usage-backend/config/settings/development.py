from .base import *  # noqa: F403

SECRET_KEY = SECRET_KEY or "development-only-key-do-not-use-in-production"  # noqa: F405
DEBUG = env_bool("DJANGO_DEBUG", False)  # noqa: F405
CSRF_COOKIE_SECURE = False
