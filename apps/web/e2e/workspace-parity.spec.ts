import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

async function mockAuthenticatedApi(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("deepscout.last_run_id", FIXTURE_RUN_ID);
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      json: { authenticated: true, mode: "local", hosted_auth_ready: true, id: "local", display_name: "Local workspace" },
    });
  });
  await page.route("**/api/v1/overview", async (route) => {
    await route.fulfill({ json: overviewFixture });
  });
  await page.route("**/api/v1/settings", async (route) => {
    await route.fulfill({ json: settingsFixture });
  });
}

async function mockHostedAnonymous(page: Page) {
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({ json: { authenticated: false, mode: "hosted" } }),
  );
  await page.route("**/api/v1/settings", async (route) =>
    route.fulfill({ json: { ui_locale: "en" } }),
  );
  await page.route("**/api/v1/overview", async (route) =>
    route.fulfill({ json: { recent: [], active: null } }),
  );
}

test.describe("workspace component parity", () => {
  test("demo and authenticated owner share research workspace structure", async ({ page }) => {
    await mockAuthenticatedApi(page);
    await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) =>
      route.fulfill({ json: workspaceFixture }),
    );
    await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) =>
      route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } }),
    );

    await page.goto(`/research/${FIXTURE_RUN_ID}`);
    await expect(page.getByTestId("app-shell")).toBeVisible();
    await expect(page.getByTestId("research-header")).toBeVisible();
    await expect(page.getByTestId("demo-shell")).toHaveCount(0);
    const sharedSelectors = [
      "[data-testid='research-header']",
      "[data-testid='technical-details']",
      ".sidebar",
    ];
    for (const selector of sharedSelectors) {
      await expect(page.locator(selector)).toBeVisible();
    }

    await mockHostedAnonymous(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}`);
    await expect(page.getByTestId("demo-shell")).toBeVisible();
    await expect(page.getByTestId("app-shell")).toHaveCount(0);
    await expect(page.getByTestId("demo-notice")).toBeVisible();
    for (const selector of sharedSelectors) {
      await expect(page.locator(selector)).toBeVisible();
    }
    await expect(page.getByTestId("demo-run-tabs")).toHaveCount(0);
  });
});
