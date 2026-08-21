import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

async function mockHostedAnonymous(page: Page) {
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({ json: { authenticated: false, mode: "hosted", hosted_auth_ready: true } }),
  );
  await page.route("**/api/v1/overview", async (route) =>
    route.fulfill({
      json: {
        ...overviewFixture,
        identity: { label: "Visitor", role: "Anonymous", mode: "hosted" },
        recent: [],
        active: null,
      },
    }),
  );
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
}

async function mockHostedAuthenticated(page: Page) {
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: {
        authenticated: true,
        mode: "hosted",
        hosted_auth_ready: true,
        id: "user-1",
        display_name: "Francesco",
      },
    }),
  );
  await page.route("**/api/v1/overview", async (route) =>
    route.fulfill({
      json: {
        ...overviewFixture,
        identity: { label: "Francesco", role: "Authenticated", mode: "hosted" },
      },
    }),
  );
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
}

test.describe("mode B public surfaces", () => {
  test("login offers GitHub, Google, and demo", async ({ page }) => {
    await mockHostedAnonymous(page);
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Welcome to Deep Scout" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Continue with GitHub/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Continue with Google/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Explore demo/ })).toBeVisible();
  });

  test("demo is read-only copy", async ({ page }) => {
    await mockHostedAnonymous(page);
    await page.goto("/demo");
    await expect(page.getByTestId("public-shell")).toBeVisible();
    await expect(page.getByTestId("app-shell")).toHaveCount(0);
    await expect(page.getByText(/No signup/)).toBeVisible();
    await expect(page.getByRole("link", { name: /Run your own research/ })).toBeVisible();
  });

  test("account secret fields stay password inputs", async ({ page }) => {
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({
        json: { authenticated: true, mode: "hosted", hosted_auth_ready: true, id: "1", display_name: "A" },
      }),
    );
    await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
    await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
    await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
    await page.route("**/api/v1/account", async (route) =>
      route.fulfill({
        json: {
          privacy: "encrypted at rest",
          credentials: [{ provider: "google", configured: true, status: "configured" }],
        },
      }),
    );
    await page.goto("/account");
    const input = page.locator("#cred-google");
    await expect(input).toHaveAttribute("type", "password");
    await expect(page.getByText(/google —/i)).toBeVisible();
    await expect(page.locator("body")).not.toContainText("sk-");
  });
});

test.describe("mode B public entry routing", () => {
  test("anonymous hosted / shows public landing without app dashboard", async ({ page }) => {
    await mockHostedAnonymous(page);
    await page.goto("/");
    await expect(page.getByTestId("public-shell")).toBeVisible();
    await expect(page.getByTestId("app-shell")).toHaveCount(0);
    await expect(page.getByTestId("landing-demo")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Welcome back/i })).toHaveCount(0);
    await expect(page.getByLabel("Primary navigation")).toHaveCount(0);
  });

  test("anonymous hosted /research/new redirects to login", async ({ page }) => {
    await mockHostedAnonymous(page);
    await page.goto("/research/new");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByTestId("public-shell")).toBeVisible();
    await expect(page.getByTestId("app-shell")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /Welcome to Deep Scout/i })).toBeVisible();
  });

  test("anonymous hosted /dashboard redirects to login", async ({ page }) => {
    await mockHostedAnonymous(page);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByTestId("app-shell")).toHaveCount(0);
  });

  test("authenticated hosted / redirects to dashboard", async ({ page }) => {
    await mockHostedAuthenticated(page);
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("app-shell")).toBeVisible();
    await expect(page.getByTestId("public-shell")).toHaveCount(0);
  });

  test("anonymous hosted demo run uses demo shell not app shell", async ({ page }) => {
    await mockHostedAnonymous(page);
    await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) =>
      route.fulfill({ json: workspaceFixture }),
    );
    await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) =>
      route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } }),
    );
    await page.goto(`/research/${FIXTURE_RUN_ID}`);
    await expect(page.getByTestId("demo-shell")).toBeVisible();
    await expect(page.getByTestId("app-shell")).toHaveCount(0);
    await expect(page.getByLabel("Primary navigation")).toHaveCount(0);
  });

  test("logout returns to public landing", async ({ page }) => {
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({
        json: { authenticated: true, mode: "hosted", hosted_auth_ready: true, id: "1", display_name: "A" },
      }),
    );
    await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
    await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
    await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
    await page.route("**/api/v1/account", async (route) =>
      route.fulfill({
        json: {
          privacy: "encrypted at rest",
          credentials: [],
        },
      }),
    );
    await page.route("**/api/v1/auth/logout", async (route) => {
      await route.fulfill({ json: { ok: true } });
      await page.route("**/api/v1/auth/me", async (meRoute) =>
        meRoute.fulfill({ json: { authenticated: false, mode: "hosted", hosted_auth_ready: true } }),
      );
    });
    await page.goto("/account");
    await page.getByRole("button", { name: "Log out", exact: true }).click();
    await expect(page).toHaveURL("/");
    await expect(page.getByTestId("public-shell")).toBeVisible();
  });
});
