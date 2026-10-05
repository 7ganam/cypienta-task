"""HTTP client for the upstream Cypienta API."""

import logging
from typing import Any

import httpx
from django.conf import settings

from .filters import TimeRange
from .validation import ValidationError, validate_record, validate_user

logger = logging.getLogger(__name__)


class UpstreamError(Exception):
    def __init__(self, message: str, status: int = 502):
        """Create an error for a failed interaction with the upstream API."""
        super().__init__(message)
        self.status = status


class CypientaClient:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        """Create a client for communicating with the Cypienta API."""
        self.transport = transport

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int = 200,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Send a request and return its JSON-decoded response."""
        if not settings.API_URL:
            raise UpstreamError("Upstream API URL is not configured", 503)
        try:
            base_url = httpx.URL(settings.API_URL)
        except httpx.InvalidURL:
            raise UpstreamError("Upstream API URL is invalid", 503) from None
        if (
            base_url.scheme not in {"http", "https"}
            or not base_url.host
            or (base_url.port is not None and not 0 <= base_url.port <= 65535)
            or base_url.userinfo
            or base_url.query
            or base_url.fragment
        ):
            raise UpstreamError("Upstream API URL is invalid", 503)
        if authenticated and not settings.API_KEY:
            raise UpstreamError("Upstream API key is not configured", 503)
        timeout = httpx.Timeout(
            settings.API_TIMEOUT_SECONDS, connect=min(5, settings.API_TIMEOUT_SECONDS)
        )
        try:
            # No redirects or retries: a retried POST could create duplicate usage.
            with httpx.Client(
                base_url=str(base_url).rstrip("/") + "/",
                timeout=timeout,
                follow_redirects=False,
                transport=self.transport,
                headers={"Accept": "application/json"},
            ) as client:
                response = client.request(
                    method,
                    path.lstrip("/"),
                    headers={"X-API-Key": settings.API_KEY} if authenticated else {},
                    **kwargs,
                )
        except httpx.TimeoutException:
            logger.warning(
                "Upstream API is not responding",
                extra={"method": method, "route": path, "status": 504},
            )
            raise UpstreamError("Upstream API is not responding", 504) from None
        except httpx.RequestError:
            logger.warning(
                "Upstream API is not responding",
                extra={"method": method, "route": path, "status": 503},
            )
            raise UpstreamError("Upstream API is not responding", 503) from None
        if response.status_code != expected_status:
            logger.warning(
                "upstream_rejected_request",
                extra={"method": method, "route": path, "status": response.status_code},
            )
            if response.status_code in {401, 403}:
                raise UpstreamError("Cypienta API authentication failed")
            if response.status_code == 429:
                raise UpstreamError("Cypienta API rate limit reached", 503)
            raise UpstreamError("Cypienta API returned an unexpected response")
        try:
            return response.json()
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise UpstreamError("Cypienta API returned invalid JSON") from None

    def user_info(self) -> dict[str, Any]:
        """Fetch and validate the current user's information."""
        payload = self._request("GET", "/api/user/info")
        try:
            return validate_user(payload)
        except ValidationError:
            raise UpstreamError("Cypienta API returned invalid user info") from None

    def actions(self, bounds: TimeRange | None = None) -> list[dict[str, Any]]:
        """Fetch and validate usage actions, optionally within a time range."""
        bounds = bounds or TimeRange()
        payload = self._request("GET", "/api/user/actions", params=bounds.as_params())
        try:
            if not isinstance(payload, list):
                raise ValidationError("Invalid usage history")
            return [validate_record(item) for item in payload]
        except ValidationError:
            raise UpstreamError("Cypienta API returned invalid usage history") from None

    def create_action(self, usage: float) -> dict[str, Any]:
        """Create a usage action in Cypienta and validate the returned record."""
        payload = self._request(
            "POST", "/api/user/actions", expected_status=201, json={"usage": usage}
        )
        try:
            return validate_record(payload)
        except ValidationError:
            raise UpstreamError("Cypienta API returned an invalid usage record") from None

    def health(self) -> None:
        """Check that the unauthenticated Cypienta health endpoint is healthy."""
        payload = self._request("GET", "/health", authenticated=False)
        if not isinstance(payload, dict) or payload.get("status") != "healthy":
            raise UpstreamError("Cypienta API is not healthy")
