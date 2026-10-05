import json
import math
import re
from datetime import UTC, datetime
from typing import Any

from django.http import HttpRequest

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:$|[Tt ])")


class ValidationError(ValueError):
    """Raised when incoming data fails schema or value validation."""


def parse_datetime(value: Any, field: str) -> datetime:
    """Parse a date or ISO 8601 datetime string into a UTC-aware datetime."""
    if not isinstance(value, str) or not ISO_DATE.match(value):
        raise ValidationError(f"{field} must be YYYY-MM-DD or an ISO 8601 datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        raise ValidationError(f"{field} must be a valid ISO 8601 date or datetime") from None


def utc_string(value: datetime) -> str:
    """Convert a datetime to a UTC ISO 8601 string with a trailing Z."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def finite_number(value: Any) -> float:
    """Validate that a value is a finite JSON-compatible number."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("usage must be a finite JSON number")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise ValidationError("usage must be a finite JSON number") from None
    if not math.isfinite(result):
        raise ValidationError("usage must be a finite JSON number")
    return result


def load_json_object(request: HttpRequest) -> dict[str, Any]:
    """Load and validate a request body as a JSON object."""
    if request.content_type != "application/json":
        raise ValidationError("Content-Type must be application/json")
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ValidationError("Request body must contain valid JSON") from None
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")
    return payload


def validate_usage(payload: dict[str, Any]) -> float:
    """Validate a usage payload and return the normalized numeric value."""
    if set(payload) != {"usage"}:
        raise ValidationError("Provide exactly one field: usage")
    value = finite_number(payload["usage"])
    if not 0 <= value <= 100:
        raise ValidationError("usage must be between 0 and 100")
    return value


def validate_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a usage record and normalize it to the API schema."""
    if not isinstance(payload, dict):
        raise ValidationError("Invalid usage record")
    identifier = payload.get("usage_id")
    if type(identifier) is not int or identifier < 1:
        raise ValidationError("Invalid usage_id")
    usage = payload.get("usage")
    if usage is None:
        raise ValidationError("Invalid usage record")
    return {
        "usage_id": identifier,
        "usage": finite_number(usage),
        "timestamp": utc_string(parse_datetime(payload.get("timestamp"), "timestamp")),
    }


def validate_user(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a user record and normalize it to the API schema."""
    if not isinstance(payload, dict):
        raise ValidationError("Invalid user info")
    identifier = payload.get("user_id")
    name = payload.get("name")
    if type(identifier) is not int or identifier < 1 or not isinstance(name, str) or not name:
        raise ValidationError("Invalid user info")
    return {
        "user_id": identifier,
        "name": name,
        "created_at": utc_string(parse_datetime(payload.get("created_at"), "created_at")),
    }
