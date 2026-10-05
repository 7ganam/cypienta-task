import logging
import re
import time
import uuid

from django.core.exceptions import SuspiciousOperation

from .errors import error_response

logger = logging.getLogger(__name__)
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied_id = request.headers.get("X-Request-ID", "")
        request.request_id = supplied_id if REQUEST_ID.fullmatch(supplied_id) else uuid.uuid4().hex
        started = time.monotonic()
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        response["Cache-Control"] = "no-store"
        match = getattr(request, "resolver_match", None)
        logger.info(
            "request_completed",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "route": match.route if match else "unmatched",
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            },
        )
        return response

    def process_exception(self, request, exception):
        # Django raises this for oversized bodies and other invalid client input.
        # Returning a generic 500 here would override Django's normal 400 handling.
        if isinstance(exception, SuspiciousOperation):
            return error_response("Bad request", 400)
        logger.error(
            "unhandled_exception",
            extra={
                "request_id": request.request_id,
                "exception_type": type(exception).__name__,
            },
        )
        return error_response("Internal server error", 500)
