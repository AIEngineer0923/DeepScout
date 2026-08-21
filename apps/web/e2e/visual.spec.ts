import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

async function mockApi(page: Page) {
  await page.addInitScript(() => {
    document.documentElement.setAttribute("data-visual", "1");
    window.localStorage.setItem("deepscout.last_run_id", "11111111-1111-4111-8111-111111111111");
    window.localStorage.setItem("deepscout.ui_locale", "en");
  });
  await page.clock.setFixedTime(new Date("2026-08-21T10:05:00.000Z"));
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) =>
    route.fulfill({ json: workspaceFixture }),
  );
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) =>
    route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } }),
  );
}

const desktop = { width: 1440, height: 900 };

test.describe("visual regression", () => {
  test.skip(({ browserName }) => browserName !== "chromium" || Boolean(process.env.CI), "Chromium local baselines; skipped in CI due to OS font rasterization");
  test.use({ viewport: desktop });

  test("dashboard desktop", async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize(desktop);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Welcome back|Bentornato/ })).toBeVisible();
    await expect(page.locator(".shell")).toHaveScreenshot("dashboard.png", { maxDiffPixelRatio: 0.03 });
  });

  test("new research desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto("/research/new");
    await expect(page.getByTestId("mode-standard")).toBeVisible();
    await expect(page.locator(".shell")).toHaveScreenshot("new-research.png", { maxDiffPixelRatio: 0.03 });
  });

  test("live research desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}`);
    await expect(page.locator(".shell")).toHaveScreenshot("live-research.png", { maxDiffPixelRatio: 0.03 });
  });

  test("workers desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/workers`);
    await expect(page.locator(".shell")).toHaveScreenshot("workers.png", { maxDiffPixelRatio: 0.03 });
  });

  test("sources desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/sources`);
    await expect(page.locator(".shell")).toHaveScreenshot("sources.png", { maxDiffPixelRatio: 0.03 });
  });

  test("claims desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/claims`);
    await expect(page.locator(".shell")).toHaveScreenshot("claims.png", { maxDiffPixelRatio: 0.03 });
  });

  test("report desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/report`);
    await expect(page.locator(".shell")).toHaveScreenshot("report.png", { maxDiffPixelRatio: 0.03 });
  });

  test("evaluations desktop", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/evaluations`);
    await expect(page.locator(".shell")).toHaveScreenshot("evaluations.png", { maxDiffPixelRatio: 0.03 });
  });

  test("mobile run 390", async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/research/${FIXTURE_RUN_ID}`);
    await expect(page.locator(".shell")).toHaveScreenshot("mobile-run.png", { maxDiffPixelRatio: 0.03 });
  });
});
