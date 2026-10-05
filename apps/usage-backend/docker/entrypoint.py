"""Generate an ephemeral secret only for the explicitly enabled local demo."""

import os
import secrets

if not os.getenv("DJANGO_SECRET_KEY") and os.getenv("DJANGO_LOCAL_DEMO") == "true":
    os.environ["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(48)

os.execvp("gunicorn", ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"])
