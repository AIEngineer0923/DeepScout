import { expect, test } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

test("mobile drawer replaces bottom navigation", async ({ page }) => {
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({ json: { authenticated: false, mode: "local", hosted_auth_ready: false } }),
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");

  await expect(page.locator(".mobile-nav")).toHaveCount(0);
  await expect(page.getByTestId("mobile-menu-button")).toBeVisible();

  await page.getByTestId("mobile-menu-button").click();
  const drawer = page.getByTestId("mobile-drawer");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("link", { name: "History" })).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Learning" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByTestId("mobile-drawer")).toHaveCount(0);
});

test("account menu logout redirects to login", async ({ page }) => {
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: { authenticated: true, mode: "local", hosted_auth_ready: false, id: "user-1" },
    }),
  );
  await page.route("**/api/v1/account", async (route) =>
    route.fulfill({ json: { email: "user@example.com", credentials: [] } }),
  );
  let logoutCalled = false;
  await page.route("**/api/v1/auth/logout", async (route) => {
    logoutCalled = true;
    await route.fulfill({ json: { status: "ok" } });
  });

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/dashboard");

  await page.getByTestId("account-menu-trigger").click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.waitForURL("**/login");
  expect(logoutCalled).toBe(true);
});

test("timeline filters map phase events to quality", async ({ page }) => {
  const runId = FIXTURE_RUN_ID;
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route(`**/api/v1/research-runs/${runId}/workspace`, async (route) =>
    route.fulfill({
      json: {
        ...workspaceFixture,
        status: "completed",
        completed_at: "2026-08-21T10:05:00.000Z",
        activity: [
          { sequence: 1, type: "phase.completed", payload: { phase: "verify" }, created_at: "2026-08-21T10:01:00.000Z" },
          { sequence: 2, type: "source.discovered", payload: { url: "https://example.com" }, created_at: "2026-08-21T10:02:00.000Z" },
        ],
      },
    }),
  );
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({ json: { authenticated: false, mode: "local", hosted_auth_ready: false } }),
  );

  await page.goto(`/research/${runId}`);
  await page.getByRole("button", { name: "Quality" }).click();
  await expect(page.getByText("Verification completed")).toBeVisible();
  await expect(page.getByText("New source discovered")).toHaveCount(0);
});
