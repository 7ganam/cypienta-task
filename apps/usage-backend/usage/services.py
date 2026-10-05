"""Usage workflows, independent of HTTP requests and responses."""

from typing import Any

from .client import CypientaClient
from .filters import TimeRange
from .validation import parse_datetime


def get_user_info() -> dict[str, Any]:
    """Fetch the current authenticated user's profile from the upstream API."""
    return CypientaClient().user_info()


def get_usage_history(bounds: TimeRange | None = None) -> list[dict[str, Any]]:
    """Fetch usage records within the requested time window."""
    effective_bounds: TimeRange = bounds or TimeRange()
    raw_records: list[dict[str, Any]] = CypientaClient().actions(effective_bounds)
    records: list[dict[str, Any]] = [
        item
        for item in raw_records
        if effective_bounds.contains(parse_datetime(item["timestamp"], "timestamp"))
    ]
    # Compare datetimes, not strings: fractional seconds are optional in ISO 8601.
    return sorted(
        records,
        key=lambda item: (parse_datetime(item["timestamp"], "timestamp"), item["usage_id"]),
        reverse=True,
    )


def create_usage_record(usage: float) -> dict[str, Any]:
    """Create a new usage record for the given numeric usage value."""
    return CypientaClient().create_action(usage)


def check_upstream_health() -> None:
    """Call the upstream health endpoint and raise if the service is unhealthy."""
    CypientaClient().health()
