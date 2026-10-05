import json
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
from django.http import QueryDict
from django.test import Client, SimpleTestCase, override_settings

from usage.client import CypientaClient
from usage.filters import PRESETS, parse_time_range
from usage.validation import ValidationError

USER = {"user_id": 1, "name": "Jane Doe", "created_at": "2026-01-15T10:30:00"}
RECORD = {"usage_id": 1, "usage": 42.7, "timestamp": "2026-01-15T10:30:00"}


class ApiTests(SimpleTestCase):
    def setUp(self):
        self.requests = []
        self.upstream_status = 200
        self.upstream_payload = USER
        self.upstream_exception = None
        self.upstream_content = None

        def handler(request):
            self.requests.append(request)
            if self.upstream_exception:
                raise self.upstream_exception
            if self.upstream_content is not None:
                return httpx.Response(self.upstream_status, content=self.upstream_content)
            return httpx.Response(self.upstream_status, json=self.upstream_payload)

        gateway = CypientaClient(transport=httpx.MockTransport(handler))
        self.gateway_patch = patch("usage.services.CypientaClient", return_value=gateway)
        self.gateway_patch.start()
        self.addCleanup(self.gateway_patch.stop)

    def test_user_info_is_normalized_and_secret_is_only_sent_upstream(self):
        self.upstream_payload = {**USER, "api_key": "sensitive"}
        response = self.client.get("/api/user/info")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**USER, "created_at": "2026-01-15T10:30:00Z"})
        self.assertEqual(self.requests[0].headers["X-API-Key"], "test-api-key")
        self.assertNotIn("api_key", response.json())
        self.assertNotIn("test-api-key", response.content.decode())
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_empty_history(self):
        self.upstream_payload = []
        self.assertEqual(self.client.get("/api/user/actions").json(), [])

    def test_history_is_sorted_by_actual_time_including_fractional_seconds(self):
        self.upstream_payload = [
            {**RECORD, "usage_id": 1, "timestamp": "2026-01-15T10:30:00Z"},
            {**RECORD, "usage_id": 2, "timestamp": "2026-01-15T10:30:00.500000Z"},
            {**RECORD, "usage_id": 3, "timestamp": "2026-01-15T12:30:00.500000+02:00"},
        ]
        response = self.client.get("/api/user/actions")
        self.assertEqual([item["usage_id"] for item in response.json()], [3, 2, 1])

    def test_custom_range_normalizes_offsets_and_enforces_inclusive_bounds(self):
        self.upstream_payload = [
            {**RECORD, "usage_id": 1, "timestamp": "2026-01-15T08:59:59Z"},
            {**RECORD, "usage_id": 2, "timestamp": "2026-01-15T09:00:00Z"},
            {**RECORD, "usage_id": 3, "timestamp": "2026-01-15T10:00:00Z"},
            {**RECORD, "usage_id": 4, "timestamp": "2026-01-15T10:00:01Z"},
        ]
        response = self.client.get(
            "/api/user/actions",
            {
                "start_date": "2026-01-15T11:00:00+02:00",
                "end_date": "2026-01-15T12:00:00+02:00",
            },
        )
        self.assertEqual([item["usage_id"] for item in response.json()], [3, 2])
        self.assertEqual(
            dict(self.requests[0].url.params),
            {"start_date": "2026-01-15T09:00:00Z", "end_date": "2026-01-15T10:00:00Z"},
        )

    def test_all_presets_produce_correct_upstream_bounds(self):
        now = datetime(2026, 10, 3, 12, tzinfo=UTC)
        self.upstream_payload = []
        with patch("usage.filters.datetime") as clock:
            clock.now.return_value = now
            for preset, duration in PRESETS.items():
                with self.subTest(preset=preset):
                    response = self.client.get("/api/user/actions", {"timeframe": preset})
                    self.assertEqual(response.status_code, 200)
                    params = self.requests[-1].url.params
                    self.assertEqual(
                        params["start_date"], (now - duration).isoformat().replace("+00:00", "Z")
                    )
                    self.assertEqual(params["end_date"], "2026-10-03T12:00:00Z")

    def test_bad_filters_are_rejected_before_network_access(self):
        invalid = [
            "timeframe=invalid",
            "start_date=garbage",
            "end_date=2026-02-30",
            "start_date=2026-02-01&end_date=2026-01-01",
            "timeframe=15m&start_date=2026-01-01",
            "unknown=1",
            "timeframe=15m&timeframe=1h",
            "start_date=",
            "timeframe=",
        ]
        for query in invalid:
            with self.subTest(query=query):
                response = self.client.get("/api/user/actions?" + query)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())
        self.assertEqual(self.requests, [])

    def test_post_valid_usage(self):
        self.upstream_status, self.upstream_payload = 201, RECORD
        response = self.client.post(
            "/api/user/actions", {"usage": 42.7}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["usage"], 42.7)
        self.assertEqual(json.loads(self.requests[0].content), {"usage": 42.7})
        self.assertEqual(self.requests[0].method, "POST")

    def test_usage_boundaries(self):
        self.upstream_status = 201
        for usage in (0, 100, 0.01, 99.99):
            with self.subTest(usage=usage):
                self.upstream_payload = {**RECORD, "usage": usage}
                response = self.client.post(
                    "/api/user/actions", {"usage": usage}, content_type="application/json"
                )
                self.assertEqual(response.status_code, 201)

    def test_invalid_usage_is_not_sent_upstream(self):
        invalid = [
            {},
            [],
            None,
            {"usage": True},
            {"usage": "42"},
            {"usage": -1},
            {"usage": 101},
            {"usage": None},
            {"usage": float("nan")},
            {"usage": float("inf")},
            {"usage": 10, "extra": 1},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/user/actions", json.dumps(payload), content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.requests, [])

    def test_malformed_json_and_wrong_content_type(self):
        for body, content_type in (
            ("{", "application/json"),
            ("\xff", "application/json"),
            ("usage=12", "text/plain"),
        ):
            with self.subTest(body=body):
                response = self.client.post("/api/user/actions", body, content_type=content_type)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.requests, [])

    def test_oversized_body_is_a_client_error(self):
        response = self.client.post(
            "/api/user/actions", " " * 20000, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.requests, [])

    @override_settings(API_URL="")
    def test_missing_url_only_blocks_upstream_requests(self):
        response = self.client.get("/api/user/info")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "Upstream API URL is not configured"})
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.requests, [])

    def test_invalid_url_is_a_request_configuration_error(self):
        for url in (
            "not-a-url",
            "ftp://upstream.test",
            "http://upstream.test:invalid",
            "http://upstream.test:65536",
            "http://upstream.test:-1",
            "http://user:secret@upstream.test",
            "http://upstream.test?key=secret",
            "http://upstream.test#fragment",
        ):
            with self.subTest(url=url), override_settings(API_URL=url):
                response = self.client.get("/api/user/info")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"error": "Upstream API URL is invalid"})
                self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.requests, [])

    @override_settings(API_KEY="")
    def test_missing_key_is_a_configuration_error(self):
        self.assertEqual(self.client.get("/api/user/info").status_code, 503)
        self.assertEqual(self.requests, [])

    def test_csrf_is_required_and_bootstrap_token_allows_post(self):
        self.upstream_status, self.upstream_payload = 201, RECORD
        browser = Client(enforce_csrf_checks=True)
        blocked = browser.post(
            "/api/user/actions", {"usage": 42.7}, content_type="application/json"
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("error", blocked.json())
        self.assertEqual(self.requests, [])
        token = browser.get("/api/csrf").json()["csrfToken"]
        response = browser.post(
            "/api/user/actions",
            {"usage": 42.7},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(browser.cookies["csrftoken"]["httponly"])

    def test_cross_origin_post_is_blocked(self):
        browser = Client(enforce_csrf_checks=True)
        token = browser.get("/api/csrf").json()["csrfToken"]
        response = browser.post(
            "/api/user/actions",
            {"usage": 42.7},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://untrusted.test",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.requests, [])

    def test_timeout_and_connection_failures_have_safe_errors(self):
        for exception, status in (
            (httpx.ReadTimeout("secret error"), 504),
            (httpx.ConnectError("secret error"), 503),
        ):
            with self.subTest(status=status):
                self.upstream_exception = exception
                response = self.client.get("/api/user/info")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"error": "Upstream API is not responding"})
                self.assertNotIn("secret", response.content.decode())

    def test_outage_keeps_local_routes_available_and_allows_recovery(self):
        self.upstream_exception = httpx.ConnectError("offline")
        for _ in range(2):
            for response in (
                self.client.get("/api/user/info"),
                self.client.get("/api/user/actions"),
                self.client.post(
                    "/api/user/actions", {"usage": 42.7}, content_type="application/json"
                ),
            ):
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"error": "Upstream API is not responding"})
            for path in ("/", "/health", "/api/csrf"):
                self.assertEqual(self.client.get(path).status_code, 200)

        self.upstream_exception = None
        response = self.client.get("/api/user/info")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], USER["user_id"])

    def test_post_timeout_is_not_retried(self):
        self.upstream_exception = httpx.ReadTimeout("upstream may already have written")
        response = self.client.post(
            "/api/user/actions", {"usage": 42.7}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 504)
        self.assertEqual(len(self.requests), 1)

    def test_upstream_errors_are_redacted(self):
        for status in (400, 401, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                self.upstream_status = status
                self.upstream_payload = {"error": "secret-api-key"}
                response = self.client.get("/api/user/info")
                self.assertEqual(response.status_code, 503 if status == 429 else 502)
                self.assertNotIn("secret-api-key", response.content.decode())

    def test_redirect_is_not_followed(self):
        self.upstream_status = 302
        response = self.client.get("/api/user/info")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(self.requests), 1)

    def test_invalid_json_upstream(self):
        self.upstream_content = b"<html>maintenance</html>"
        self.assertEqual(self.client.get("/api/user/info").status_code, 502)

    def test_wrong_upstream_shapes(self):
        for path, payload in (
            ("/api/user/info", []),
            ("/api/user/info", {**USER, "user_id": True}),
            ("/api/user/info", {**USER, "created_at": "nonsense"}),
            ("/api/user/actions", {}),
            ("/api/user/actions", [{}]),
            ("/api/user/actions", [{**RECORD, "usage": float("nan")}]),
        ):
            with self.subTest(payload=payload):
                # HTTPX deliberately rejects non-finite JSON, so pass raw content here.
                self.upstream_content = json.dumps(payload).encode()
                self.assertEqual(self.client.get(path).status_code, 502)

    def test_invalid_create_response_is_not_reported_as_success(self):
        self.upstream_status, self.upstream_payload = 201, {}
        response = self.client.post(
            "/api/user/actions", {"usage": 42.7}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(self.requests), 1)

    def test_liveness_does_not_call_upstream(self):
        self.upstream_exception = httpx.ConnectError("offline")
        self.assertEqual(self.client.get("/health").json(), {"status": "healthy"})
        self.assertEqual(self.requests, [])

    def test_readiness_checks_upstream_without_api_key(self):
        self.upstream_payload = {"status": "healthy"}
        response = self.client.get("/health/ready")
        self.assertEqual(response.json(), {"status": "ready"})
        self.assertNotIn("X-API-Key", self.requests[0].headers)
        self.upstream_exception = httpx.ConnectError("offline")
        self.assertEqual(self.client.get("/health/ready").status_code, 503)

    def test_readiness_rejects_unhealthy_response(self):
        self.upstream_payload = {"status": "unhealthy"}
        self.assertEqual(self.client.get("/health/ready").status_code, 503)

    def test_unknown_routes_and_unsupported_methods_are_json(self):
        self.assertEqual(self.client.get("/api/missing").json(), {"error": "Not found"})
        self.assertEqual(self.client.get("/api/user/info/").status_code, 404)
        response = self.client.put("/api/user/actions", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET, POST")

    def test_request_ids_are_validated(self):
        response = self.client.get("/health", HTTP_X_REQUEST_ID="demo-request-1")
        self.assertEqual(response["X-Request-ID"], "demo-request-1")
        response = self.client.get("/health", HTTP_X_REQUEST_ID="invalid id!")
        self.assertRegex(response["X-Request-ID"], r"^[a-f0-9]{32}$")

    def test_unhandled_exception_is_sanitized(self):
        with patch("usage.services.CypientaClient", side_effect=RuntimeError("secret")):
            response = self.client.get("/api/user/info")
        self.assertEqual(response.json(), {"error": "Internal server error"})
        self.assertEqual(response.status_code, 500)


class DateTests(SimpleTestCase):
    def test_date_only_bounds_mean_utc_midnight(self):
        bounds = parse_time_range(QueryDict("start_date=2026-01-15&end_date=2026-01-16"))
        self.assertEqual(
            bounds.as_params(),
            {"start_date": "2026-01-15T00:00:00Z", "end_date": "2026-01-16T00:00:00Z"},
        )

    def test_single_bound_and_naive_utc_datetime(self):
        bounds = parse_time_range(QueryDict("end_date=2026-01-15T12:00:00"))
        self.assertEqual(bounds.as_params(), {"end_date": "2026-01-15T12:00:00Z"})

    def test_utc_conversion_overflow_is_validation_error(self):
        with self.assertRaises(ValidationError):
            parse_time_range(QueryDict("start_date=0001-01-01T00:00:00%2B01:00"))
