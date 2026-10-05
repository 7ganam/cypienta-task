# Local Cypienta API mock

A standalone Django server implementing the Cypienta user API contract.
It stores usage in a simple `usage.json` file and never calls the remote API.

## Run locally

### Docker

The mock owns its Dockerfile, dependencies, and container settings. Its image
builds from this directory without any files from the backend project.
From the repository root:

```sh
docker compose up --build -d --wait mock-cypienta-api
curl http://127.0.0.1:40759/health
docker compose stop mock-cypienta-api
```

Compose publishes port `40759` on localhost and persists records in the
`mock-data` volume. The backend only receives an upstream URL and API key;
Compose selects this mock by default for the local demo. To run the backend
against another upstream without starting the mock, configure `API_URL` and
`API_KEY` in the root `.env` and run `docker compose up --build -d usage-backend`.

### Python

Requires Python 3.10+ with `venv` and `pip`. From the task root:

```sh
cd apps/mock-cypienta-api
./run.sh
```

The script creates `.venv`, installs dependencies, and
starts the server at **http://127.0.0.1:40759**.
Stop with Ctrl+C. Records persist in `usage.json` between restarts. No database
or migrations are needed. The file is a plain JSON array of usage records and
is created automatically on the first POST or seed command.
The launcher selects an installed Python 3.10+ automatically; you can choose one
explicitly with `PYTHON_BIN=python3.14 ./run.sh`.

Optional settings: copy `.env.example` to `.env` before running the script and
edit `MOCK_API_KEY` or `MOCK_API_PORT`. The `.env` file uses shell assignment
syntax. With no `.env`, environment variables work too:

```sh
MOCK_API_PORT=40759 MOCK_API_KEY=local-dev-key ./run.sh
```

For manual setup:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py runserver 127.0.0.1:40759
```

Use a compatible executable such as `python3.14` in the first command if your
system's `python3` is older than 3.10.

Manual Django commands read exported environment variables; only `run.sh`
loads `.env` automatically.

## Configure the backend

Keep the application's upstream URL and key in environment variables:

```dotenv
API_URL=http://127.0.0.1:40759
API_KEY=local-dev-key
```

Append the existing paths to `API_URL` and send `X-API-Key: <API_KEY>` on every
user request. When integrating the real server, change only these settings:

```dotenv
API_URL=http://139.177.194.233:5000
API_KEY=<your upstream API key>
```

The dummy key works only on this mock. The real key is not copied into this
server. If your application backend runs in Docker while the mock runs on the
host, use `http://host.docker.internal:40759` on Docker Desktop and start the
mock manually with `manage.py runserver 0.0.0.0:40759`; also add
`host.docker.internal` to `ALLOWED_HOSTS` in `mock_cypienta_api/settings.py`.

## Endpoints

Paths have **no trailing slash**, as in the provided collection.

| Method | Path                | Authentication | Response                                    |
| ------ | ------------------- | -------------- | ------------------------------------------- |
| GET    | `/health`           | None           | `200`, `{"status":"healthy"}`               |
| GET    | `/api/user/info`    | `X-API-Key`    | `200`, `{user_id, name, created_at}`        |
| POST   | `/api/user/actions` | `X-API-Key`    | `201`, `{usage_id, usage, timestamp}`       |
| GET    | `/api/user/actions` | `X-API-Key`    | `200`, array of usage records, newest first |

The user info is `{"user_id":1,"name":"Jane Doe","created_at":"2026-01-15T10:30:00"}`.
POST accepts `Content-Type: application/json` with `{"usage":42.7}`. Each call
creates a new persistent record with an integer ID and the current UTC time.
The GET response is a plain array, including `[]` when empty, without pagination
or an envelope. Timestamps are ISO 8601 in UTC without a timezone suffix, as in
the supplied examples; interpret them as UTC in the application.

GET accepts optional `start_date` and `end_date`: `YYYY-MM-DD`, a naive ISO
datetime (interpreted as UTC), or an ISO datetime with `Z` or a timezone offset.
Bounds are inclusive. A date alone represents midnight UTC, including for
`end_date`; use a complete datetime to express your desired upper bound.
URL-encode timezone offsets (`+` becomes `%2B`) when constructing query strings.

Missing/incorrect keys return `401`. Invalid JSON, usage, or date filters return
`400`; unknown paths return `404`; unexpected server errors return `500`.
Errors always use `{"error":"..."}`. Unsupported methods return `405` in that
same shape, with an `Allow` header. User endpoints use header authentication and
do not require cookies or CSRF tokens.

## Try it

```sh
curl http://127.0.0.1:40759/health
curl -H 'X-API-Key: local-dev-key' http://127.0.0.1:40759/api/user/info
curl -X POST http://127.0.0.1:40759/api/user/actions \
  -H 'X-API-Key: local-dev-key' -H 'Content-Type: application/json' \
  -d '{"usage":42.7}'
curl -G http://127.0.0.1:40759/api/user/actions \
  -H 'X-API-Key: local-dev-key' \
  --data-urlencode 'start_date=2026-01-01T00:00:00Z' \
  --data-urlencode 'end_date=2026-12-31T23:59:59.999999Z'
```

You can also import the supplied Postman collection and set its `base_url` to
`http://127.0.0.1:40759` and `user_api_key` to `local-dev-key`.

## Bruno collection

In Bruno, choose **Open Collection**, select the `bruno/` folder inside this
server, and select the **local** environment. The collection contains
`bruno.json`, `environments/local.bru`, request folders,
and `.bru` files with JavaScript tests.

Run the whole collection, or send individual requests. It includes health,
user info, adding usage, usage history, custom date filters, and five error
checks. Edit `base_url`, `api_key`, `usage`, `start_date`, and `end_date` in the
environment. Date defaults cover 2000–2100; set your own UTC range to narrow it.
Running the collection adds one usage record. History tests check that this
record is returned when you run the requests in sequence.

With the mock server running, the CLI equivalent is:

```sh
cd bruno
pnpm --package=@usebruno/cli@4.2.0 dlx bru run --env local
```

If you already have the CLI installed, use `bru run --env local`. To run only
the user requests, use `bru run user --env local` from the collection folder.
When switching to the real API, duplicate the environment and change `base_url`
and `api_key`. Error checks reflect this mock's validation rules; validate those
against the live API before relying on them. No real API key is stored here.

## Sample data and tests

Usage history starts empty. Add **1,000 samples spanning the last 365 days**,
with dense recent activity for all seven time presets and sparser older history
for custom ranges:

```sh
.venv/bin/python manage.py seed_usage
.venv/bin/python manage.py seed_usage --count 50 --days 1
.venv/bin/python manage.py test
```

The default data includes zero and 100 values, small decimals, spikes, rising
and falling usage, a flat stretch 45–55 minutes ago, and duplicate timestamps
with distinct IDs. Samples land just inside, on, and outside preset boundaries,
plus either side of UTC midnight and the start of the month. There are deliberate
gaps 3–4 days and 30–35 days ago for testing quiet periods and empty results.
All usage values remain within 0–100; no records are in the future.
Small custom datasets may omit some scenarios. Generation is repeatable relative
to the current time; rerun the command when you need fresh recent samples.

The contract tests use a checked-in Postman fixture in `usage_api/fixtures/`,
with the original requests and local URL/key placeholders. Private challenge
inputs are not needed to run tests from a clean checkout.

Seeding is additive. To reset local records, stop the server, delete
`usage.json`, and run `./run.sh` again. Tests use separate temporary JSON files.

## Compatibility limits

This mock represents one user. It accepts finite JSON numbers, rejects booleans
and numeric strings, ignores extra JSON fields and unrelated query parameters,
and uses the date rules above. Validation and error text can differ from the
real upstream. The intended caller is the Django backend; admin routes and
browser CORS are not implemented.

Django references: [JSON responses](https://docs.djangoproject.com/en/5.2/ref/request-response/#jsonresponse-objects)
and [custom error views](https://docs.djangoproject.com/en/5.2/topics/http/views/#customizing-error-views).
