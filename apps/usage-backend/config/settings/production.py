import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 50 characters")
if not os.getenv("DJANGO_ALLOWED_HOSTS") or "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("Set explicit DJANGO_ALLOWED_HOSTS in production")

HTTPS_ENABLED = env_bool("DJANGO_HTTPS", True)  # noqa: F405
SECURE_SSL_REDIRECT = HTTPS_ENABLED
SECURE_REDIRECT_EXEMPT = [r"^health(?:/ready)?$"]
CSRF_COOKIE_SECURE = HTTPS_ENABLED
SESSION_COOKIE_SECURE = HTTPS_ENABLED
SECURE_HSTS_SECONDS = 31536000 if HTTPS_ENABLED else 0
# Enable only if every subdomain is HTTPS and the domain is eligible for preload.
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)  # noqa: F405
SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)  # noqa: F405
# Set only behind a trusted proxy that replaces client-supplied forwarding headers.
if env_bool("DJANGO_TRUST_PROXY", False):  # noqa: F405
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
