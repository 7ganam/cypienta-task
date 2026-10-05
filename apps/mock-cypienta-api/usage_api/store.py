import json
from datetime import timezone
from pathlib import Path
from threading import RLock

from django.conf import settings

_lock = RLock()


def utc_timestamp(timestamp):
    return timestamp.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def read_records():
    with _lock:
        path = Path(settings.USAGE_FILE)
        return json.loads(path.read_text()) if path.exists() else []


def add_records(entries):
    with _lock:
        records = read_records()
        next_id = max((record["usage_id"] for record in records), default=0) + 1
        added = [
            {"usage_id": next_id + index, "usage": entry["usage"], "timestamp": entry["timestamp"]}
            for index, entry in enumerate(entries)
        ]
        path = Path(settings.USAGE_FILE)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(records + added, indent=2, allow_nan=False) + "\n")
        temporary.replace(path)
        return added
