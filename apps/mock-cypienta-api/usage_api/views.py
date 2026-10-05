import json
import math
import re
from datetime import datetime, timezone
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare
from django.utils import timezone as django_timezone

from . import store


def error(message, status):
    return JsonResponse({"error": message}, status=status)


def endpoint(*methods, authenticated=True):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if authenticated and not constant_time_compare(
                request.headers.get("X-API-Key", ""), settings.MOCK_API_KEY
            ):
                return error("Invalid or missing API key", 401)
            if request.method not in methods:
                response = error("Method not allowed", 405)
                response["Allow"] = ", ".join(methods)
                return response
            return view(request, *args, **kwargs)

        return wrapped

    return decorate


@endpoint("GET", authenticated=False)
def health(request):
    return JsonResponse({"status": "healthy"})


@endpoint("GET")
def user_info(request):
    return JsonResponse(settings.MOCK_USER)


def parse_date(value, parameter):
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[Tt ])", value):
        raise ValueError(f"{parameter} must be YYYY-MM-DD or an ISO 8601 datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError(
            f"{parameter} must be YYYY-MM-DD or an ISO 8601 datetime"
        ) from None


@endpoint("GET", "POST")
def actions(request):
    if request.method == "POST":
        if request.content_type != "application/json":
            return error("Request body must be application/json", 400)
        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            return error("Request body must contain valid JSON", 400)
        if not isinstance(payload, dict) or "usage" not in payload:
            return error("usage is required", 400)
        value = payload["usage"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return error("usage must be a finite number", 400)
        try:
            value = float(value)
        except (OverflowError, ValueError):
            return error("usage must be a finite number", 400)
        if not math.isfinite(value):
            return error("usage must be a finite number", 400)
        record = store.add_records([
            {"usage": value, "timestamp": store.utc_timestamp(django_timezone.now())}
        ])[0]
        return JsonResponse(record, status=201)

    bounds = {}
    try:
        for parameter in ("start_date", "end_date"):
            if parameter in request.GET:
                bounds[parameter] = parse_date(request.GET[parameter], parameter)
    except ValueError as exc:
        return error(str(exc), 400)
    if (
        "start_date" in bounds
        and "end_date" in bounds
        and bounds["start_date"] > bounds["end_date"]
    ):
        return error("start_date must be before or equal to end_date", 400)

    records = []
    for record in store.read_records():
        timestamp = datetime.fromisoformat(record["timestamp"]).replace(tzinfo=timezone.utc)
        if "start_date" in bounds and timestamp < bounds["start_date"]:
            continue
        if "end_date" in bounds and timestamp > bounds["end_date"]:
            continue
        records.append(record)
    records.sort(key=lambda record: (record["timestamp"], record["usage_id"]), reverse=True)
    return JsonResponse(records, safe=False)


def bad_request(request, exception):
    return error("Bad request", 400)


def permission_denied(request, exception):
    return error("Forbidden", 403)


def not_found(request, exception):
    return error("Not found", 404)


def server_error(request):
    return error("Internal server error", 500)
