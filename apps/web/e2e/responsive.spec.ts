import { expect, test } from "@playwright/test";
import { overviewFixture, settingsFixture } from "./fixtures";

const WIDTHS = [320, 360, 375, 390, 430, 768, 820, 1024, 1280, 1440, 1920];

test("no horizontal overflow at representative widths", async ({ page }) => {
  await page.addInitScript(() => {
    document.documentElement.setAttribute("data-visual", "1");
  });
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/research/new");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `width ${width}`).toBeLessThanOrEqual(1);
  }
});

test("Italian chrome does not overflow at compact widths", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("deepscout.ui_locale", "it");
    document.cookie = "deepscout.ui_locale=it; path=/";
  });
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  for (const width of [320, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/research/new");
    await expect(page.getByRole("heading", { name: "Nuova ricerca" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `it width ${width}`).toBeLessThanOrEqual(1);
  }
});
