const allowedRoutes: Record<string, string[]> = {
  "/api/user/info": ["GET"],
  "/api/user/actions": ["GET", "POST"],
  "/api/csrf": ["GET"],
};

function error(message: string, status: number) {
  return Response.json(
    { error: message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

/** Same-origin bridge to Django. Django owns validation, filters and upstream auth. */
export async function proxyRequest(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  const methods = allowedRoutes[incoming.pathname];
  if (!methods) return error("Endpoint not found", 404);
  if (!methods.includes(request.method))
    return error("Method not allowed", 405);

  // Validate the browser origin before translating it to the Django origin.
  const origin = request.headers.get("origin");
  if (request.method === "POST" && origin && origin !== incoming.origin) {
    return error("Cross-origin requests are not allowed", 403);
  }

  let backend: URL;
  try {
    backend = new URL(process.env.BACKEND_URL || "http://127.0.0.1:41873");
    if (
      !["http:", "https:"].includes(backend.protocol) ||
      backend.username ||
      backend.password ||
      backend.search ||
      backend.hash
    ) {
      return error("The backend URL is not configured correctly", 500);
    }
  } catch {
    return error("The backend URL is not configured correctly", 500);
  }
  const target = new URL(incoming.pathname + incoming.search, backend);
  const headers = new Headers({ Accept: "application/json" });
  for (const name of ["content-type", "cookie", "x-csrftoken"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (request.method === "POST") {
    headers.set("Origin", backend.origin);
    headers.set("Referer", `${backend.origin}/`);
  }
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "POST" ? await request.text() : undefined,
      signal: AbortSignal.timeout(15_000),
      redirect: "error",
    });
    const outgoing = new Headers({
      "Content-Type":
        response.headers.get("content-type") || "application/json",
      "Cache-Control": "no-store",
    });
    for (const name of ["x-request-id", "allow"]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of response.headers.getSetCookie())
      outgoing.append("Set-Cookie", cookie);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch (cause) {
    const timeout = cause instanceof Error && cause.name === "TimeoutError";
    return error(
      timeout
        ? "The backend took too long to respond. Refresh history before retrying a simulation."
        : "Cannot reach the Django backend. Check that it is running.",
      timeout ? 504 : 503,
    );
  }
}
