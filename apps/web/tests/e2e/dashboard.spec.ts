import { test, expect, type Page } from "@playwright/test";

const user = {
  user_id: 1,
  name: "Jane Doe",
  created_at: "2026-01-15T10:30:00Z",
};
const sampleRecords = () => [
  {
    usage_id: 2,
    usage: 78.25,
    timestamp: new Date(Date.now() - 5 * 60_000).toISOString(),
  },
  {
    usage_id: 1,
    usage: 24.5,
    timestamp: new Date(Date.now() - 10 * 60_000).toISOString(),
  },
];

async function mockApi(
  page: Page,
  options: {
    empty?: boolean;
    historyError?: boolean;
    postError?: boolean;
  } = {},
) {
  const records = options.empty ? [] : sampleRecords();
  const requests: { method: string; path: string; body: unknown }[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push({
      method: request.method(),
      path: url.pathname + url.search,
      body: request.postDataJSON(),
    });
    if (url.pathname === "/api/user/info") return route.fulfill({ json: user });
    if (url.pathname === "/api/csrf")
      return route.fulfill({ json: { csrfToken: "test-csrf" } });
    if (request.method() === "POST") {
      if (options.postError)
        return route.fulfill({
          status: 503,
          json: { error: "Backend unavailable" },
        });
      const record = {
        usage_id: 3,
        usage: request.postDataJSON().usage,
        timestamp: new Date().toISOString(),
      };
      records.unshift(record);
      return route.fulfill({ status: 201, json: record });
    }
    return options.historyError
      ? route.fulfill({ status: 503, json: { error: "Backend unavailable" } })
      : route.fulfill({ json: records });
  });
  return { records, requests, options };
}

test("loads user information and plots usage records in the chart", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Jane Doe" })).toBeVisible();
  await expect(page.locator(".navbar-user")).toContainText("User ID #001");
  await expect(page.locator(".navbar-user")).toContainText(
    "Member since Jan 15, 2026",
  );
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(page.getByTestId("usage-chart")).toHaveAttribute(
    "aria-label",
    /2 records/,
  );
});

test("simulation POSTs a random 0–100 value and refreshes user and history", async ({
  page,
}) => {
  const api = await mockApi(page);
  await page.goto("/");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  const before = api.requests.length;
  const posted = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/api/user/actions"),
  );
  await page
    .getByRole("button", { name: "Simulate Usage", exact: true })
    .click();
  const request = await posted;
  expect(request.postDataJSON().usage).toBeGreaterThanOrEqual(0);
  expect(request.postDataJSON().usage).toBeLessThanOrEqual(100);
  expect(request.headers()["x-csrftoken"]).toBe("test-csrf");
  await expect(page.getByRole("status")).toContainText(
    "Your dashboard is up to date",
  );
  await expect(page.getByTestId("usage-chart")).toHaveAttribute(
    "aria-label",
    /3 records/,
  );
  await expect(
    page.getByRole("button", { name: "Simulate Usage", exact: true }),
  ).toBeEnabled();
  expect(
    api.requests
      .slice(before)
      .filter(
        (request) =>
          request.method === "GET" && request.path === "/api/user/info",
      ),
  ).toHaveLength(1);
  expect(
    api.requests
      .slice(before)
      .filter(
        (request) =>
          request.method === "GET" &&
          request.path.startsWith("/api/user/actions"),
      ),
  ).toHaveLength(1);
});

test("all seven presets request their matching backend filter", async ({
  page,
}) => {
  await mockApi(page);
  const initialResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).searchParams.get("timeframe") === "7d",
  );
  await page.goto("/");
  await initialResponse;
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "7d", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  for (const preset of ["15m", "30m", "1h", "3h", "12h", "1d"]) {
    const response = page.waitForResponse(
      (response) =>
        new URL(response.url()).searchParams.get("timeframe") === preset,
    );
    await page.getByRole("button", { name: preset, exact: true }).click();
    await response;
    await expect(
      page.getByRole("button", { name: preset, exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
  }
});

test("custom ranges send UTC bounds, wait for Apply, and switch back to presets", async ({
  page,
}) => {
  await mockApi(page);
  const historyRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "GET" &&
      new URL(request.url()).pathname === "/api/user/actions"
    ) {
      historyRequests.push(request.url());
    }
  });
  await page.route("**/api/user/actions?*", async (route) => {
    if (!new URL(route.request().url()).searchParams.has("start_date"))
      return route.fallback();
    return route.fulfill({
      json: [{ usage_id: 10, usage: 52, timestamp: "2026-10-03T06:30:00Z" }],
    });
  });
  await page.goto("/");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(page.locator('input[type="datetime-local"]')).toHaveCount(0);
  const before = historyRequests.length;
  const custom = page.getByRole("button", {
    name: "Custom range",
    exact: true,
  });
  await custom.click();
  await expect(custom).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#range-timezone")).toHaveText(
    "Times in Africa/Cairo",
  );
  await page.getByLabel("Start date and time").fill("2026-10-03T09:00");
  await page.getByLabel("End date and time").fill("2026-10-03T12:00");
  expect(historyRequests).toHaveLength(before);

  const response = page.waitForResponse((response) =>
    new URL(response.url()).searchParams.has("start_date"),
  );
  await page.getByRole("button", { name: "Apply range", exact: true }).click();
  const url = new URL((await response).url());
  expect(url.searchParams.get("start_date")).toBe("2026-10-03T06:00:00.000Z");
  expect(url.searchParams.get("end_date")).toBe("2026-10-03T09:00:00.000Z");
  expect(url.searchParams.has("timeframe")).toBe(false);
  await expect(custom).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("usage-chart")).toHaveAttribute(
    "aria-label",
    /1 record/,
  );
  await expect(page.locator(".chart-meta")).toContainText("Custom range");
  await page.screenshot({
    path: "test-results/dashboard-custom-range.png",
    fullPage: true,
  });

  const appliedFooter = await page.locator(".chart-footer").textContent();
  const appliedRequests = historyRequests.length;
  await page.getByLabel("End date and time").fill("2026-10-03T13:00");
  await expect(page.locator(".chart-footer")).toHaveText(appliedFooter!);
  expect(historyRequests).toHaveLength(appliedRequests);

  const presetResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).searchParams.get("timeframe") === "1h",
  );
  await page.getByRole("button", { name: "1h", exact: true }).click();
  const presetUrl = new URL((await presetResponse).url());
  expect(presetUrl.searchParams.has("start_date")).toBe(false);
  expect(presetUrl.searchParams.has("end_date")).toBe(false);
  await expect(page.locator('input[type="datetime-local"]')).toHaveCount(0);
  await expect(custom).toHaveAttribute("aria-pressed", "false");
  await expect(
    page.getByRole("button", { name: "1h", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("invalid custom ranges show validation without fetching history", async ({
  page,
}) => {
  const api = await mockApi(page);
  await page.goto("/");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await page.getByRole("button", { name: "Custom range", exact: true }).click();
  const requests = api.requests.length;
  await page.getByLabel("Start date and time").fill("2026-10-03T12:00");
  await page.getByLabel("End date and time").fill("2026-10-03T09:00");
  await page.getByRole("button", { name: "Apply range", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "The end date must be on or after the start date.",
  );
  await expect(page.getByLabel("End date and time")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(api.requests).toHaveLength(requests);

  await page.getByLabel("Start date and time").fill("");
  await page.getByRole("button", { name: "Apply range", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Choose a valid start and end date.",
  );
  expect(api.requests).toHaveLength(requests);

  await page.getByRole("button", { name: "7d", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.locator('input[type="datetime-local"]')).toHaveCount(0);
});

test("filters preserve the minimal dashboard copy", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(page.locator(".subtitle")).toHaveCount(0);
  await expect(page.locator(".chart-card .section-heading p")).toHaveCount(0);
  await expect(page.locator(".filter-label")).toHaveCount(0);
  await expect(page.locator(".workspace-label")).toHaveCount(0);
});

test("empty history shows an honest empty state and simulation adds a record", async ({
  page,
}) => {
  await mockApi(page, { empty: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "A fresh start" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Simulate Usage", exact: true })
    .click();
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(page.getByTestId("usage-chart")).toHaveAttribute(
    "aria-label",
    /1 record/,
  );
});

test("backend history failure offers retry and recovers", async ({ page }) => {
  const api = await mockApi(page, { historyError: true });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Backend unavailable");
  await expect(
    page.getByRole("heading", { name: "Your chart is unavailable" }),
  ).toBeVisible();
  api.options.historyError = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a failed simulation is never automatically retried", async ({ page }) => {
  const api = await mockApi(page, { postError: true });
  await page.goto("/");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await page
    .getByRole("button", { name: "Simulate Usage", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Refresh activity before trying again",
  );
  expect(
    api.requests.filter((request) => request.method === "POST"),
  ).toHaveLength(1);
});

test("mobile layout keeps controls visible without horizontal page overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "7d", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Custom range", exact: true }).click();
  await expect(page.getByLabel("Start date and time")).toBeInViewport();
  await expect(page.getByLabel("End date and time")).toBeInViewport();
  await expect(
    page.getByRole("button", { name: "Apply range", exact: true }),
  ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
});

test("live Django integration saves and rereads the newly created record", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.E2E_LIVE_BACKEND !== "1",
    "Opt in against a Django backend configured to use the local mock.",
  );
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Jane Doe" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Refresh", exact: true }),
  ).toBeEnabled();
  const posted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/user/actions"),
  );
  await page
    .getByRole("button", { name: "Simulate Usage", exact: true })
    .click();
  const response = await posted;
  expect(response.status()).toBe(201);
  const created = await response.json();
  await expect(page.getByRole("status")).toContainText("Saved");
  await expect(page.getByTestId("usage-chart")).toBeVisible();
  const reread = await request.get("/api/user/actions?timeframe=1h");
  expect(reread.status()).toBe(200);
  expect(await reread.json()).toContainEqual(created);
  await page.getByRole("button", { name: "Dismiss notification" }).click();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
});
