from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.http import QueryDict

from .validation import ValidationError, parse_datetime, utc_string

PRESETS: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "3h": timedelta(hours=3),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
}


@dataclass(frozen=True)
class TimeRange:
    """Represents a start/end window for time-based filtering."""

    start: datetime | None = None
    end: datetime | None = None

    def as_params(self) -> dict[str, str]:
        """Return the range expressed as query-string parameters for API calls."""
        return {
            key: utc_string(value)
            for key, value in (("start_date", self.start), ("end_date", self.end))
            if value is not None
        }

    def contains(self, timestamp: datetime) -> bool:
        """Return whether a timestamp falls within the inclusive time range."""
        return (self.start is None or timestamp >= self.start) and (
            self.end is None or timestamp <= self.end
        )


def parse_time_range(query: QueryDict, *, now: datetime | None = None) -> TimeRange:
    """Parse allowed usage query parameters into a validated inclusive time range."""
    allowed: set[str] = {"timeframe", "start_date", "end_date"}
    if set(query) - allowed:
        raise ValidationError("Supported filters are timeframe, start_date, end_date")

    for key in query:
        if len(query.getlist(key)) != 1 or not query[key]:
            raise ValidationError(f"{key} must have exactly one non-empty value")

    if "timeframe" in query:
        if "start_date" in query or "end_date" in query:
            raise ValidationError("Use either timeframe or custom date filters")

        timeframe_value = query.get("timeframe")
        if not isinstance(timeframe_value, str):
            raise ValidationError("timeframe must be a valid string")

        preset = timeframe_value
        if preset not in PRESETS:
            raise ValidationError("timeframe must be one of: " + ", ".join(PRESETS))

        preset_end: datetime = now or datetime.now(UTC)
        return TimeRange(preset_end - PRESETS[preset], preset_end)

    start: datetime | None = (
        parse_datetime(query["start_date"], "start_date") if "start_date" in query else None
    )
    end: datetime | None = (
        parse_datetime(query["end_date"], "end_date") if "end_date" in query else None
    )
    if start is not None and end is not None and start > end:
        raise ValidationError("start_date must be before or equal to end_date")

    return TimeRange(start, end)
