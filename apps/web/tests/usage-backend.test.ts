import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { proxyRequest } from "../src/server/usage-backend";

describe("usage-backend proxy", () => {
  beforeEach(() => vi.stubEnv("BACKEND_URL", ""));
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("uses the local Django URL without environment configuration and preserves filters", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json([]));
    const response = await proxyRequest(
      new Request("http://localhost:3000/api/user/actions?timeframe=15m"),
    );
    expect(response.status).toBe(200);
    expect(fetch.mock.calls[0][0].toString()).toBe(
      "http://127.0.0.1:41873/api/user/actions?timeframe=15m",
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });

  it("forwards CSRF cookie, token and JSON body while rewriting the verified origin", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        Response.json({ usage_id: 1, usage: 42.7 }, { status: 201 }),
      );
    const response = await proxyRequest(
      new Request("http://localhost:3000/api/user/actions", {
        method: "POST",
        headers: {
          Origin: "http://localhost:3000",
          Cookie: "csrftoken=cookie",
          "X-CSRFToken": "token",
          "Content-Type": "application/json",
          "X-API-Key": "do-not-forward",
        },
        body: '{"usage":42.7}',
      }),
    );
    const options = fetch.mock.calls[0][1]!;
    const headers = options.headers as Headers;
    expect(headers.get("Origin")).toBe("http://127.0.0.1:41873");
    expect(headers.get("cookie")).toBe("csrftoken=cookie");
    expect(headers.get("x-csrftoken")).toBe("token");
    expect(headers.has("x-api-key")).toBe(false);
    expect(options.body).toBe('{"usage":42.7}');
    expect(response.status).toBe(201);
  });

  it("returns Set-Cookie from the CSRF setup endpoint to the browser", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        { csrfToken: "token" },
        {
          headers: {
            "Set-Cookie": "csrftoken=cookie; Path=/; HttpOnly; SameSite=Lax",
          },
        },
      ),
    );
    const response = await proxyRequest(
      new Request("http://localhost:3000/api/csrf"),
    );
    expect(response.headers.get("Set-Cookie")).toContain("csrftoken=cookie");
  });

  it("rejects cross-origin POSTs before reaching Django", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    const response = await proxyRequest(
      new Request("http://localhost:3000/api/user/actions", {
        method: "POST",
        headers: { Origin: "https://another-site.example" },
        body: '{"usage":20}',
      }),
    );
    expect(response.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("limits the proxy to the required endpoints and methods", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    expect(
      (await proxyRequest(new Request("http://localhost:3000/api/private")))
        .status,
    ).toBe(404);
    expect(
      (
        await proxyRequest(
          new Request("http://localhost:3000/api/user/info", {
            method: "POST",
          }),
        )
      ).status,
    ).toBe(405);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("preserves backend validation errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ error: "Invalid range" }, { status: 400 }),
    );
    const response = await proxyRequest(
      new Request("http://localhost:3000/api/user/actions?timeframe=wrong"),
    );
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "Invalid range" });
  });

  it("returns a useful unavailable response without retrying a failed POST", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValue(new TypeError("connect ECONNREFUSED"));
    const response = await proxyRequest(
      new Request("http://localhost:3000/api/user/actions", {
        method: "POST",
        body: '{"usage":10}',
      }),
    );
    expect(response.status).toBe(503);
    expect((await response.json()).error).toContain("Django backend");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
