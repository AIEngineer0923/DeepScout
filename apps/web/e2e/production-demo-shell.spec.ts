import { expect, test } from "@playwright/test";

const BASE = process.env.PRODUCTION_URL ?? "https://deep-scout-plum.vercel.app";
const describeProductionUx = process.env.CI && !process.env.PRODUCTION_E2E ? test.describe.skip : test.describe;

describeProductionUx("production demo shell", () => {
  test("sidebar research navigation is active for published run", async ({ page }) => {
    const catalog = await page.request.get(`${BASE}/api/v1/demos`);
    const demos = (await catalog.json()).items;
    const runId = demos[0].id as string;
    await page.goto(`${BASE}/research/${runId}/plan`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 20_000 });
    const plan = page.getByRole("link", { name: /plan|piano/i }).first();
    await expect(plan).toBeVisible();
    await page.getByRole("link", { name: /report/i }).first().click();
    await expect(page).toHaveURL(new RegExp(`/research/${runId}/report`));
  });

  test("mobile demo report has no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const catalog = await page.request.get(`${BASE}/api/v1/demos`);
    const runId = (await catalog.json()).items[0].id as string;
    await page.goto(`${BASE}/research/${runId}/report`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 20_000 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    expect(overflow).toBeFalsy();
  });
});
