import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "local-mock-cypienta-development-only"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
INSTALLED_APPS = ["usage_api"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "mock_cypienta_api.urls"
WSGI_APPLICATION = "mock_cypienta_api.wsgi.application"
APPEND_SLASH = False
DATABASES = {}
USAGE_FILE = BASE_DIR / "usage.json"
TIME_ZONE = "UTC"
USE_TZ = True

MOCK_API_KEY = os.environ.get("MOCK_API_KEY", "local-dev-key")
if not MOCK_API_KEY:
    raise ValueError("MOCK_API_KEY must not be empty")
MOCK_USER = {
    "user_id": 1,
    "name": "Jane Doe",
    "created_at": "2026-01-15T10:30:00",
}
