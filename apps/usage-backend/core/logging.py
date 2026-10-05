import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Allowlisted metadata: never serialize request headers, bodies, or secrets."""

    def format(self, record):
        event = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in ("request_id", "method", "route", "status", "duration_ms", "exception_type"):
            if hasattr(record, field):
                event[field] = getattr(record, field)
        # Django's message text can include paths and raw exception values.
        if record.name.startswith("django"):
            event["event"] = "django_error"
        if record.exc_info and record.exc_info[0] is not None:
            event["exception_type"] = record.exc_info[0].__name__
        return json.dumps(event)
