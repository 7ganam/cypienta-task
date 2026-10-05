import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, override_settings

from . import store


class JsonFileTestCase(SimpleTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.usage_file = Path(temporary.name) / "usage.json"
        settings = override_settings(USAGE_FILE=self.usage_file)
        settings.enable()
        self.addCleanup(settings.disable)


@override_settings(MOCK_API_KEY="test-api-key")
class ApiContractTests(JsonFileTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(headers={"X-API-Key": "test-api-key"})

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(set(response.json()), {"error"})
        self.assertIsInstance(response.json()["error"], str)

    def create_record(self, usage, timestamp):
        return store.add_records([{"usage": usage, "timestamp": store.utc_timestamp(timestamp)}])[0]

    def test_health_is_public_and_exact(self):
        for client in (Client(), Client(headers={"X-API-Key": "incorrect"})):
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "healthy"})

    def test_user_info_matches_the_reference_shape(self):
        response = self.client.get("/api/user/info")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"user_id": 1, "name": "Jane Doe", "created_at": "2026-01-15T10:30:00"},
        )

    def test_all_user_operations_require_the_configured_key(self):
        for key in (None, "incorrect", "local-dev-key"):
            client = Client() if key is None else Client(headers={"X-API-Key": key})
            for path in ("/api/user/info", "/api/user/actions"):
                with self.subTest(key=key, path=path):
                    self.assert_error(client.get(path), 401)
            self.assert_error(
                client.post("/api/user/actions", {"usage": 42}, content_type="application/json"),
                401,
            )
        self.assertEqual(store.read_records(), [])

    def test_post_and_get_round_trip_without_csrf_or_cookies(self):
        client = Client(enforce_csrf_checks=True, headers={"X-API-Key": "test-api-key"})
        before = datetime.now(timezone.utc)
        response = client.post(
            "/api/user/actions", {"usage": 42.7}, content_type="application/json"
        )
        after = datetime.now(timezone.utc)
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(set(payload), {"usage_id", "usage", "timestamp"})
        self.assertIsInstance(payload["usage_id"], int)
        self.assertEqual(payload["usage"], 42.7)
        timestamp = datetime.fromisoformat(payload["timestamp"])
        self.assertIsNone(timestamp.tzinfo)
        self.assertLessEqual(before, timestamp.replace(tzinfo=timezone.utc))
        self.assertLessEqual(timestamp.replace(tzinfo=timezone.utc), after)
        self.assertEqual(client.get("/api/user/actions").json(), [payload])
        self.assertEqual(json.loads(self.usage_file.read_text()), [payload])

    def test_empty_history_is_a_plain_array(self):
        response = self.client.get("/api/user/actions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_newest_first_with_id_tiebreaker(self):
        older = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newer = older + timedelta(days=1)
        first = self.create_record(10, newer)
        oldest = self.create_record(20, older)
        last = self.create_record(30, newer)
        records = self.client.get("/api/user/actions").json()
        self.assertEqual(
            [item["usage_id"] for item in records],
            [last["usage_id"], first["usage_id"], oldest["usage_id"]],
        )

    def test_usage_accepts_finite_numbers_without_undocumented_range_limits(self):
        for value in (0, 100, 42.7, -1, 101):
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/user/actions", {"usage": value, "extra": "ignored"},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["usage"], value)

    def test_missing_or_invalid_usage_returns_400_without_writes(self):
        payloads = [
            {}, [], None, {"usage": None}, {"usage": True}, {"usage": False},
            {"usage": "42"}, {"usage": {}}, {"usage": []},
            {"usage": float("nan")}, {"usage": float("inf")},
            {"usage": -float("inf")}, {"usage": 10**400},
        ]
        for payload in payloads:
            with self.subTest(payload=repr(payload)):
                response = self.client.post(
                    "/api/user/actions", json.dumps(payload), content_type="application/json"
                )
                self.assert_error(response, 400)
        self.assertEqual(store.read_records(), [])

    def test_malformed_body_returns_json_400(self):
        for body in (b"{", b"", b"\xff"):
            with self.subTest(body=body):
                response = self.client.post(
                    "/api/user/actions", body, content_type="application/json"
                )
                self.assert_error(response, 400)

    def test_json_content_type_is_required(self):
        self.assert_error(
            self.client.post("/api/user/actions", '{"usage":42}', content_type="text/plain"),
            400,
        )

    def test_charset_in_json_content_type_is_supported(self):
        response = self.client.post(
            "/api/user/actions", '{"usage":42}', content_type="application/json; charset=utf-8"
        )
        self.assertEqual(response.status_code, 201)

    def test_date_filters_are_inclusive_and_keep_newest_first(self):
        start = datetime(2026, 1, 16, 14, 20, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        self.create_record(1, start - timedelta(microseconds=1))
        first = self.create_record(2, start)
        last = self.create_record(3, end)
        self.create_record(4, end + timedelta(microseconds=1))
        response = self.client.get(
            "/api/user/actions",
            {"start_date": "2026-01-16T14:20:00Z", "end_date": "2026-01-16T15:20:00Z"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["usage_id"] for item in response.json()], [last["usage_id"], first["usage_id"]]
        )

    def test_date_only_bounds_mean_midnight_utc(self):
        midnight = datetime(2026, 1, 16, tzinfo=timezone.utc)
        included = self.create_record(1, midnight)
        self.create_record(2, midnight + timedelta(hours=1))
        response = self.client.get(
            "/api/user/actions", {"start_date": "2026-01-16", "end_date": "2026-01-16"}
        )
        self.assertEqual([item["usage_id"] for item in response.json()], [included["usage_id"]])

    def test_naive_and_offset_datetimes_match_the_same_utc_record(self):
        record = self.create_record(1, datetime(2026, 1, 16, 14, 20, tzinfo=timezone.utc))
        for bound in ("2026-01-16T14:20:00", "2026-01-16T17:20:00+03:00"):
            with self.subTest(bound=bound):
                response = self.client.get(
                    "/api/user/actions", {"start_date": bound, "end_date": bound}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["usage_id"] for item in response.json()], [record["usage_id"]])

    def test_either_date_bound_can_be_used_alone(self):
        first = self.create_record(1, datetime(2026, 1, 15, tzinfo=timezone.utc))
        last = self.create_record(2, datetime(2026, 1, 17, tzinfo=timezone.utc))
        after = self.client.get("/api/user/actions", {"start_date": "2026-01-16"}).json()
        before = self.client.get("/api/user/actions", {"end_date": "2026-01-16"}).json()
        self.assertEqual([item["usage_id"] for item in after], [last["usage_id"]])
        self.assertEqual([item["usage_id"] for item in before], [first["usage_id"]])

    def test_invalid_dates_return_json_400(self):
        for parameter in ("start_date", "end_date"):
            for value in ("", "not-a-date", "2026-02-30", "20260116", "2026-01-16T25:00:00"):
                with self.subTest(parameter=parameter, value=value):
                    self.assert_error(self.client.get("/api/user/actions", {parameter: value}), 400)

    def test_reversed_range_returns_json_400(self):
        self.assert_error(
            self.client.get(
                "/api/user/actions", {"start_date": "2026-01-17", "end_date": "2026-01-16"}
            ),
            400,
        )

    def test_unknown_paths_and_trailing_slashes_return_json_404_without_redirect(self):
        for path in ("/unknown", "/health/", "/api/user/info/", "/api/user/actions/"):
            with self.subTest(path=path):
                self.assert_error(self.client.get(path), 404)

    def test_unsupported_methods_return_json_405(self):
        for path, method, allowed in (
            ("/health", "post", "GET"),
            ("/api/user/info", "post", "GET"),
            ("/api/user/actions", "delete", "GET, POST"),
        ):
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method)(path)
                self.assert_error(response, 405)
                self.assertEqual(response["Allow"], allowed)

    def test_server_errors_keep_the_json_error_shape(self):
        client = Client(raise_request_exception=False, headers={"X-API-Key": "test-api-key"})
        with patch("usage_api.views.store.read_records", side_effect=RuntimeError("internal")):
            response = client.get("/api/user/actions")
        self.assert_error(response, 500)
        self.assertEqual(response.json(), {"error": "Internal server error"})

    def test_supplied_postman_requests_work_with_only_url_and_key_replaced(self):
        collection_path = Path(__file__).with_name("fixtures") / "postman_user_collection.json"
        collection = json.loads(collection_path.read_text())
        for item in collection["item"]:
            request = item["request"]
            path = "/" + "/".join(request["url"]["path"])
            with self.subTest(name=item["name"]):
                if request["method"] == "POST":
                    response = self.client.post(
                        path, request["body"]["raw"], content_type="application/json"
                    )
                    self.assertEqual(response.status_code, 201)
                else:
                    query = {item["key"]: item["value"] for item in request["url"].get("query", [])}
                    response = self.client.get(path, query)
                    self.assertEqual(response.status_code, 200)


class SeedUsageTests(JsonFileTestCase):
    def test_seed_adds_data_for_the_short_and_long_time_filters(self):
        instant = datetime(2026, 1, 16, 14, 20, tzinfo=timezone.utc)
        with patch("usage_api.management.commands.seed_usage.timezone.now", return_value=instant):
            call_command("seed_usage", stdout=StringIO())
        records = store.read_records()
        self.assertEqual(len(records), 1000)
        timestamps = [datetime.fromisoformat(record["timestamp"]).replace(tzinfo=timezone.utc) for record in records]
        self.assertEqual(max(timestamps), instant)
        self.assertEqual(min(timestamps), instant - timedelta(days=365))
        for minutes in (15, 30, 60, 180, 720, 1440, 10080):
            with self.subTest(minutes=minutes):
                self.assertGreater(sum(timestamp >= instant - timedelta(minutes=minutes) for timestamp in timestamps), 5)
        call_command("seed_usage", count=1, days=1, stdout=StringIO())
        self.assertEqual(len(store.read_records()), 1001)

    def test_seed_includes_value_edges_plateaus_duplicates_gaps_and_utc_boundaries(self):
        instant = datetime(2026, 1, 16, 14, 20, tzinfo=timezone.utc)
        with patch("usage_api.management.commands.seed_usage.timezone.now", return_value=instant):
            call_command("seed_usage", stdout=StringIO())
        records = store.read_records()
        values = [record["usage"] for record in records]
        self.assertEqual(min(values), 0)
        self.assertEqual(max(values), 100)
        self.assertIn(0.01, values)
        self.assertIn(99.99, values)
        ages = [instant - datetime.fromisoformat(record["timestamp"]).replace(tzinfo=timezone.utc) for record in records]
        plateau = [record for record, age in zip(records, ages) if timedelta(minutes=45) <= age <= timedelta(minutes=55)]
        self.assertGreaterEqual(len(plateau), 6)
        self.assertEqual({record["usage"] for record in plateau}, {50.0})
        for start, end in ((3, 4), (30, 35)):
            self.assertFalse(any(timedelta(days=start) < age < timedelta(days=end) for age in ages))
        self.assertLess(len({(record["timestamp"], record["usage"]) for record in records}), len(records))
        self.assertEqual(len({record["usage_id"] for record in records}), len(records))
        timestamps = {record["timestamp"] for record in records}
        for boundary in (instant.replace(hour=0, minute=0), instant.replace(day=1, hour=0, minute=0)):
            for seconds in (-1, 0, 1):
                self.assertIn(store.utc_timestamp(boundary + timedelta(seconds=seconds)), timestamps)

    def test_custom_seed_count_and_range_are_respected(self):
        instant = datetime(2026, 1, 16, 14, 20, tzinfo=timezone.utc)
        with patch("usage_api.management.commands.seed_usage.timezone.now", return_value=instant):
            call_command("seed_usage", count=50, days=1, stdout=StringIO())
        records = store.read_records()
        self.assertEqual(len(records), 50)
        timestamps = [datetime.fromisoformat(record["timestamp"]).replace(tzinfo=timezone.utc) for record in records]
        self.assertEqual(min(timestamps), instant - timedelta(days=1))
        self.assertEqual(max(timestamps), instant)
        self.assertTrue(all(0 <= record["usage"] <= 100 for record in records))

    def test_seed_is_repeatable_with_the_same_reference_time(self):
        instant = datetime(2026, 1, 16, 14, 20, tzinfo=timezone.utc)
        with patch("usage_api.management.commands.seed_usage.timezone.now", return_value=instant):
            call_command("seed_usage", stdout=StringIO())
            expected = store.read_records()
            self.usage_file.unlink()
            call_command("seed_usage", stdout=StringIO())
        self.assertEqual(store.read_records(), expected)

    def test_invalid_seed_options_are_rejected(self):
        for options in ({"count": 0}, {"days": 0}, {"days": -1}, {"days": float("nan")}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command("seed_usage", stdout=StringIO(), **options)
        self.assertEqual(store.read_records(), [])


@override_settings(MOCK_API_KEY="test-api-key")
class JsonPersistenceTests(JsonFileTestCase):
    def test_existing_json_is_loaded_and_ids_continue_after_restart(self):
        existing = {"usage_id": 8, "usage": 42.7, "timestamp": "2026-01-16T14:20:00"}
        self.usage_file.write_text(json.dumps([existing]))
        client = Client(headers={"X-API-Key": "test-api-key"})
        self.assertEqual(client.get("/api/user/actions").json(), [existing])
        response = client.post("/api/user/actions", {"usage": 10}, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["usage_id"], 9)
        self.assertEqual(json.loads(self.usage_file.read_text()), [existing, response.json()])

    def test_overlapping_writes_keep_every_record_and_unique_ids(self):
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(
                lambda value: store.add_records([{"usage": value, "timestamp": "2026-01-16T14:20:00"}]),
                range(20),
            ))
        records = json.loads(self.usage_file.read_text())
        self.assertEqual(len(records), 20)
        self.assertEqual({record["usage_id"] for record in records}, set(range(1, 21)))
        self.assertEqual({record["usage"] for record in records}, set(range(20)))
