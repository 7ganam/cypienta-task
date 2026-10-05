# usage-backend

A Django backend for the Usage Dashboard. It calls the upstream Cypienta API
or the local `mock-cypienta-api` substitute.
It fetches user information, records usage, and processes time filters against
the upstream configured by `API_URL` and `API_KEY`. `../web/` contains the dashboard UI.

## Start locally

Python 3.12+ is required. Configure the backend's external upstream:

```sh
cp apps/usage-backend/.env.example apps/usage-backend/.env
```

The example configures the local mock at `http://127.0.0.1:40759` with
`API_KEY=local-dev-key`. Start it with `pnpm dev:mock-cypienta-api`, or set
`API_URL` and `API_KEY` for your external upstream. Exported variables override
`.env`. Without configuration, there is no default upstream URL or key.
The key is never returned to the browser.

From the repository root, install dependencies and start only Django:

```sh
sh apps/usage-backend/run.sh --setup
pnpm dev:usage-backend
```

The backend runs at **http://127.0.0.1:41873**. Open `/` for endpoint discovery
or `/health` for liveness. `/health/ready` checks the configured upstream.
The backend needs no database or migrations: the upstream stores the records.
Django starts even when upstream configuration is missing or the upstream is
unavailable; only requests that depend on it fail.

## API

Paths have no trailing slash. Responses are JSON; errors use `{"error":"..."}`.

| Method | Path                | Behavior                                       |
| ------ | ------------------- | ---------------------------------------------- |
| GET    | `/`                 | Service and endpoint discovery                 |
| GET    | `/api/user/info`    | User ID, name, creation time                   |
| GET    | `/api/user/actions` | Usage records, newest first; plain array       |
| POST   | `/api/user/actions` | Record `{"usage":42.7}`; returns 201           |
| GET    | `/api/csrf`         | Set CSRF cookie and return `csrfToken`         |
| GET    | `/health`           | Process liveness; never calls the upstream     |
| GET    | `/health/ready`     | Checks upstream health; returns 503 on failure |

`usage` must be a finite JSON number between 0 and 100. Booleans, numeric
strings, extra fields, and malformed JSON are rejected before contacting the
upstream.

### Time filters

```text
/api/user/actions?timeframe=15m
/api/user/actions?timeframe=30m
/api/user/actions?timeframe=1h
/api/user/actions?timeframe=3h
/api/user/actions?timeframe=12h
/api/user/actions?timeframe=1d
/api/user/actions?timeframe=7d
/api/user/actions?start_date=2026-01-15T10:00:00Z&end_date=2026-01-16T10:00:00Z
```

Use a preset **or** a custom range. Custom ranges allow either or both bounds.
Bounds are inclusive. Dates alone mean midnight UTC, including `end_date`;
send a complete datetime for another end time. Naive datetimes are interpreted
as UTC; explicit timezone offsets are converted to UTC. URL-encode `+` in
offsets. Every returned timestamp includes `Z` so JavaScript interprets UTC
correctly. The backend validates, filters, and sorts upstream records.

### Browser integration

Serve the UI from the same origin, or use its dev server to proxy `/api` to
this backend. The browser never needs `X-API-Key`. POSTs require a CSRF cookie
and the token returned by `/api/csrf`:

```js
const { csrfToken } = await fetch("/api/csrf").then((r) => r.json());
const usage = Math.floor(Math.random() * 10001) / 100;
const response = await fetch("/api/user/actions", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
  body: JSON.stringify({ usage }),
});
if (!response.ok) throw new Error((await response.json()).error);
const created = await response.json();
const history = await fetch("/api/user/actions?timeframe=1h").then((r) =>
  r.json(),
);
```

For a frontend dev proxy, set `DJANGO_CSRF_TRUSTED_ORIGINS` to the frontend
origin, for example `http://localhost:5173`. Prefer this proxy over adding
permissive CORS. This is a single-user backend with no application login;
the upstream key selects the user.

### Error behavior

Invalid input returns 400; failed CSRF returns 403; unknown routes return 404;
unsupported methods return 405 with `Allow`. Upstream authentication failures,
malformed payloads, redirects, and unexpected statuses return 502. Upstream
connection failures/rate limits return 503, and timeouts return 504. Connection
failures and timeouts return `{"error":"Upstream API is not responding"}` and log
the same message on stderr. Missing or invalid upstream configuration returns
503 with a configuration error. Django keeps running, and `/`, `/health`, and
`/api/csrf` remain available. Requests can succeed again when the upstream
recovers. Raw upstream error text is never exposed. POSTs are never automatically
retried: after a timeout, refresh history before deciding whether to try again,
since the upstream may have already saved the record.

## Structure

```text
config/              Django URL routing, WSGI/ASGI, environment settings
core/                JSON errors, request IDs, structured logging
usage/client.py      Upstream HTTP calls and response validation
usage/services.py    Usage creation, history filtering and sorting
usage/validation.py  JSON, numeric, and datetime validation
usage/filters.py     Presets and custom ranges
usage/views.py       Thin endpoint handlers
usage/tests/         Isolated endpoint / integration-contract tests
docker/              Container entrypoint
k8s/                 Deployment, Service, ConfigMap, and Secret template
../../.github/       Tests, lint, and Docker builds for all apps
```

Requests flow through **view → service → upstream client**. Views validate request
input and build HTTP responses; services coordinate usage operations; the client
handles upstream HTTP calls and validates upstream responses. Cypienta owns storage.

Logs are JSON on stderr with request ID, method, route, status, and duration.
`X-Request-ID` is validated or generated and returned in responses. Request
bodies, query values, API keys, and raw upstream errors are excluded. Unexpected
errors log their exception type; reproduce locally to investigate the details.

## Tests and lint

### Bruno collection

To import this collection into the Bruno desktop app:

1. Start the backend using the local or Docker instructions above.
2. Open Bruno and click the **+** beside **Collections** in the left sidebar.
3. Choose **Open collection**. This is the option for an existing native Bruno
   collection; **Import collection** is used for other collection formats.
4. Select this project's **`bruno/` folder** (`apps/usage-backend/bruno/` from the
   task root), then click **Open**. Select the folder containing `bruno.json`.
   On macOS, **Cmd+Shift+G** in the folder picker lets you enter its path.
5. Select **usage-backend** in the sidebar. Open the environment
   selector at the top right, choose the **Collection** tab, and select **local**.
6. Open **Setup → Health Check** and click **Send**. Expect HTTP **200** with
   `{"status":"healthy"}`. Before sending POSTs individually, send
   **Setup → Get CSRF Token** to initialize the token and cookie.

The **local** environment uses `http://127.0.0.1:41873`, for either the local
Django run or Docker Compose. The collection contains `bruno.json`, a local
environment, request folders, and response tests.

The collection covers endpoint discovery, liveness/readiness, user info,
creation, history, custom ranges, all seven time presets, and
expected validation/CSRF/404/405 errors. **Run Setup → Get CSRF Token first** before
sending POST requests individually; it stores the token and cookie as runtime
variables. The dedicated Setup folder runs before the User and Errors folders
in a full collection run, including in the CLI.
No API key belongs in this collection: Django supplies its upstream key.

Edit `usage`, `start_date`, and `end_date` in the local environment. A full run
creates one persistent upstream record and then verifies it in history.
With the backend configured to use a test upstream, run the CLI equivalent:

```sh
cd bruno
pnpm --package=@usebruno/cli@4.2.0 dlx bru run --env local
```

If the CLI is already installed, use `bru run --env local`.

### Django tests

From `apps/usage-backend`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/python manage.py check
.venv/bin/python manage.py test --settings=config.settings.test
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

With the backend and a configured test upstream running, exercise the full HTTP flow:

```sh
python3 scripts/smoke_test.py
```

This intentionally creates one upstream record and verifies it through a fresh
history request. Use an upstream where test writes are appropriate.

If using `uv`, install with `uv pip sync --python .venv/bin/python requirements-dev.txt`.
`run.sh` installs runtime dependencies and preserves installed development tools.
Tests mock HTTP transport and never call or write to the real API. They cover
the endpoints, all presets, UTC conversion, sort order, validation, CSRF,
body limits, upstream failures, secret redaction, and health probes.
See [DEBUGGING.md](DEBUGGING.md) for the Kubernetes crash loop caused by an
invalid Django secret key.

## Docker

### usage-backend only

From `apps/usage-backend`, optionally copy `.env.example` to `.env` and set `API_URL` and
`API_KEY` for your external upstream, then run:

```sh
docker compose up
```

This builds and starts **only Django**, at **http://localhost:41873**. It uses
this folder's Compose file and build context, without a dependency on another
project or service. Configuration comes from exported variables or this folder's
`.env`; there is no default upstream URL or key. The Bruno **local** environment
uses this backend address.

The standalone Compose project and service are both named `usage-backend`.
Its image, `usage-backend:local`, is also used by the root Compose stack and
the Kubernetes Deployment.

The container starts and stays healthy even when the upstream is unavailable.
Upstream requests log and return **Upstream API is not responding** (503 for
connection failures, 504 for timeouts). Missing URL/key or an invalid URL returns
a configuration error on dependent requests. `/health` remains 200; the separate
`/health/ready` probe reports 503 while the upstream is unavailable. No upstream
request is made during server startup or the container's liveness check.

Django runs as a non-root user with a read-only filesystem. Compose enables local
HTTP mode and generates an ephemeral Django secret if one is not supplied.
Run `docker compose down` from this folder to stop Django, or
`docker compose up --build` after changing application code.

The full dashboard's startup instructions are in the [root README](../../README.md).
It shares the backend host port, so stop that stack before starting this one.

### Production settings

For production, supply `DJANGO_SETTINGS_MODULE=config.settings.production`,
a random `DJANGO_SECRET_KEY` of at least 50 characters and explicit
`DJANGO_ALLOWED_HOSTS`. Set `API_URL` and `API_KEY` for upstream requests. Leave
`DJANGO_LOCAL_DEMO` unset. HTTPS is enabled by default; terminate TLS at a trusted proxy and enable
`DJANGO_TRUST_PROXY=true` only when that proxy replaces forwarded headers.
`DJANGO_HTTPS=false` is intended for local HTTP demos.

Generate a secret with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.
Run `python manage.py check --deploy --settings=config.settings.production`
against deployment settings. HSTS subdomains/preload require separate opt-in.

## Kubernetes and CI

The manifests include two replicas, startup/readiness/liveness probes, CPU and
memory requests/limits, and a non-root container with a read-only filesystem.
`k8s/secret.yaml` documents the required Secret fields with placeholders.
The setup guides create the populated Secret from a private env file and apply
the remaining resources with Kustomize; do not commit real credentials.

Follow the [backend-only deployment guide](k8s/README.md) or the
[full dashboard deployment guide](../../k8s/demo/README.md). Both use the real
upstream API. To use another upstream, change `API_URL` in `k8s/kustomization.yaml`.
No cluster is required for local development.

The root [CI workflow](../../.github/workflows/ci.yml) runs lint and tests and
builds all three Docker images on pushes and pull requests.

References: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/),
[Django CSRF](https://docs.djangoproject.com/en/5.2/howto/csrf/),
[HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/).
