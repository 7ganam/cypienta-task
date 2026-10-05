# Cypienta usage dashboard

A React + TypeScript **TanStack Start** application in `apps/web`. It talks
to the Django backend in `apps/usage-backend` through server routes and uses TanStack Query to
fetch and refresh data. Recharts renders the timestamped usage records.

## Run

Requires Node.js **22.12+** and Python **3.12+**. From the repository root:

```sh
pnpm install --frozen-lockfile
pnpm run setup
cp apps/usage-backend/.env.example apps/usage-backend/.env
pnpm dev
```

This starts all three apps. Use `pnpm dev:web` to start just this app.
Open **http://127.0.0.1:3000**. The app defaults to the Django server at
**http://127.0.0.1:41873**. To change it, copy this app's `.env.example` to `.env` and set
`BACKEND_URL`, or export that environment variable. Restart after changing it.
`BACKEND_URL` is the Django URL; Django configures the upstream `API_URL` and
`API_KEY`. The frontend does not contain or need the upstream API key.

## Dashboard

- **User information:** displays the name, user ID and account creation date
  returned by `GET /api/user/info`.
- **Simulate Usage:** generates a random number from 0 through 100, obtains a
  CSRF token, then sends `{"usage": value}` to `POST /api/user/actions`.
  A successful POST refreshes both user information and usage history.
- **Usage chart:** plots records from `GET /api/user/actions` in chronological
  order, with a datetime axis and exact values in tooltips.
- **Time filters:** 15m, 30m, 1h, 3h, 12h, 1d and 7d send Django's `timeframe`
  parameter. Choose **Custom range**, enter the start and end in the displayed
  local timezone, then click **Apply range**. The inputs validate ordering and
  send `start_date` and `end_date` as ISO UTC datetimes. Selecting a preset
  returns to a relative time window.

The UI includes record counts, refresh/retry controls, loading and empty states,
error feedback and a mobile layout. All
displayed dates use the browser's local timezone, shown below the chart.
Usage is labeled in units because the API does not define it as a percentage.
A new simulation outside a fixed custom range is saved but excluded from that
range, and the notification explains this.

## How the connection works

Browser → TanStack Start `/api/*` server routes → Django → Cypienta/mock API.

The Start proxy allowlists the three needed API paths, forwards Django's CSRF
cookie and token, and returns Django's status and JSON errors. Before rewriting
the origin for Django, it rejects browser POSTs from a different origin.
This works in development and the production Node build without browser CORS
configuration or changes to Django's trusted origins. Django continues to own
validation, filtering, upstream authentication and data processing.

POSTs are never automatically retried: a timeout may occur after the backend
has saved a record. Refresh history before deciding to simulate again.

## Production build

```sh
pnpm build
pnpm start
```

Nitro produces a runnable Node server in `.output/`. It uses port 3000 by
default; set `PORT` to change it. The start command reads `.env` if present.
The Django backend remains a separate running service. Build output and
`node_modules` are excluded from version control and submission archives.

## Tests

```sh
pnpm build
pnpm typecheck
pnpm test:web
pnpm --filter ./apps/web exec playwright install chromium
pnpm test:e2e
```

Unit tests cover presets, local-to-UTC date conversion, statistics and the
server proxy's CSRF/origin/error behavior. Browser tests cover the four frontend
requirements, empty/error/retry states and mobile overflow using intercepted
API responses.

To exercise the entire HTTP chain **against Django configured with the local
mock** (this creates one persistent mock record):

```sh
E2E_LIVE_BACKEND=1 pnpm test:e2e
```

To test a running production build, set `E2E_BASE_URL`, e.g.
`E2E_BASE_URL=http://127.0.0.1:3001 pnpm test:e2e`. The live test confirms the
201 response, the rendered record and a separate history reread. Screenshots
are saved under `test-results/`. See `DEBUGGING.md` for a bug found while
connecting the app.

Framework setup follows the official [TanStack Start setup](https://tanstack.com/start/latest/docs/framework/react/build-from-scratch),
[server routes](https://tanstack.com/start/latest/docs/framework/react/guide/server-routes)
and [Nitro hosting](https://tanstack.com/start/latest/docs/framework/react/guide/hosting) documentation.
