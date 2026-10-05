"""Settings for the standalone mock container."""

from pathlib import Path

from .settings import *  # noqa: F403

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "mock-cypienta-api"]
USAGE_FILE = Path("/data/usage.json")