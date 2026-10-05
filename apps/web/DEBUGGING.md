# Missing environment variable broke the default connection

**Symptom:** The UI rendered, but both user info and history returned HTTP 500:
`The backend URL is not configured correctly`.

**Investigation:** A direct request to Django returned valid JSON. Requests to
the same paths through Start returned the configuration error before any
backend request. Inspection narrowed the issue to the Vite environment setup.

**Root cause:** `process.env.BACKEND_URL ??= env.BACKEND_URL` assigned JavaScript
`undefined` when no `.env` existed. Node coerces values assigned to `process.env`
into strings, so the proxy received the truthy string `"undefined"` instead of
using its default local Django URL.

**Fix:** Assign the loaded value only when it exists. Restart the dev process
to remove the invalid value already present in its environment.

**Prevention:** The proxy test verifies its default URL without environment
configuration. The live browser test starts without a required `.env` and
verifies a POST plus an independent history reread through the full proxy.
