from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token

from core.errors import error_response

from . import services
from .client import UpstreamError
from .filters import PRESETS, parse_time_range
from .validation import ValidationError, load_json_object, validate_usage


def endpoint(*methods: str) -> Callable[[Callable[..., JsonResponse]], Callable[..., JsonResponse]]:
    """Enforce allowed methods and return expected failures as JSON."""

    def decorate(view: Callable[..., JsonResponse]) -> Callable[..., JsonResponse]:
        @wraps(view)
        def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
            if request.method not in methods:
                response = error_response("Method not allowed", 405)
                response["Allow"] = ", ".join(methods)
                return response
            try:
                return view(request, *args, **kwargs)
            except ValidationError as exc:
                return error_response(str(exc), 400)
            except UpstreamError as exc:
                return error_response(str(exc), exc.status)

        return wrapped

    return decorate


@endpoint("GET")
def index(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "service": "usage-backend",
            "endpoints": {
                "user": "/api/user/info",
                "actions": "/api/user/actions",
                "csrf": "/api/csrf",
                "liveness": "/health",
                "readiness": "/health/ready",
            },
            "timeframes": list(PRESETS),
        }
    )


@endpoint("GET")
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy"})


@endpoint("GET")
def readiness(request: HttpRequest) -> JsonResponse:
    try:
        services.check_upstream_health()
    except UpstreamError:
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})


@endpoint("GET")
def csrf(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"csrfToken": get_token(request)})


@endpoint("GET")
def user_info(request: HttpRequest) -> JsonResponse:
    return JsonResponse(services.get_user_info())


@endpoint("GET", "POST")
def actions(request: HttpRequest) -> JsonResponse:
    if request.method == "POST":
        usage = validate_usage(load_json_object(request))
        return JsonResponse(services.create_usage_record(usage), status=201)
    bounds = parse_time_range(request.GET)
    return JsonResponse(services.get_usage_history(bounds), safe=False)
