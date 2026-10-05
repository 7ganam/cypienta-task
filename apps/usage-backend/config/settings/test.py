from .base import *  # noqa: F403

SECRET_KEY = "tests-only-not-a-real-secret"
API_URL = "http://upstream.test"
API_KEY = "test-api-key"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CSRF_COOKIE_SECURE = False
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
}
