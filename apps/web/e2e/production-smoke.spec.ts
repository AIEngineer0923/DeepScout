import { expect, test } from "@playwright/test";

const BASE = process.env.PRODUCTION_URL ?? "https://deep-scout-plum.vercel.app";

test.describe("production public demo smoke", () => {
  test("anonymous landing shows public shell", async ({ page }) => {
    await page.goto(`${BASE}/`);
    await expect(page.getByTestId("public-shell")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: /explore live demo|esplora demo live/i })).toBeVisible();
  });

  test("anonymous /dashboard redirects to login", async ({ page }) => {
    await page.goto(`${BASE}/dashboard`);
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });

  test("anonymous /research/new redirects to login", async ({ page }) => {
    await page.goto(`${BASE}/research/new`);
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });

  test("demo catalog loads from API", async ({ page }) => {
    await page.goto(`${BASE}/demo`);
    await expect(page.getByTestId("public-shell")).toBeVisible({ timeout: 15_000 });
    const res = await page.request.get(`${BASE}/api/v1/demos`);
    expect(res.ok()).toBeTruthy();
  });
});
