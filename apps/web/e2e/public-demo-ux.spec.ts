import { expect, test } from "@playwright/test";

const BASE = process.env.PRODUCTION_URL ?? "https://deep-scout-plum.vercel.app";
const describeProductionUx = process.env.CI && !process.env.PRODUCTION_E2E ? test.describe.skip : test.describe;

describeProductionUx("public demo UX", () => {
  test("demo shell has single tab row and no raw events", async ({ page }) => {
    const catalog = await page.request.get(`${BASE}/api/v1/demos`);
    const demos = (await catalog.json()).items;
    test.skip(demos.length === 0, "no published demos");
    const runId = demos[0].id as string;

    await page.goto(`${BASE}/research/${runId}`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("demo-run-tabs")).toHaveCount(1);
    await expect(page.getByTestId("research-header")).toBeVisible();
    await expect(page.getByTestId("demo-notice")).toBeVisible();
    await expect(page.getByTestId("technical-details")).toBeVisible();
    await expect(page.getByText(/run\.completed/i)).toHaveCount(0);
  });

  test("technical details disclosure works", async ({ page }) => {
    const catalog = await page.request.get(`${BASE}/api/v1/demos`);
    const runId = (await catalog.json()).items[0].id as string;
    await page.goto(`${BASE}/research/${runId}`);
    await page.getByTestId("technical-details").getByRole("button").click();
    await expect(page.getByText(/gemini|google|openai/i)).toBeVisible();
  });

  test("locale switch reloads localized presentation", async ({ page, context }) => {
    await context.addCookies([
      { name: "deepscout.ui_locale", value: "it", domain: new URL(BASE).hostname, path: "/" },
    ]);
    const catalog = await page.request.get(`${BASE}/api/v1/demos`, {
      headers: { "X-UI-Locale": "it" },
    });
    const item = (await catalog.json()).items[0];
    await page.goto(`${BASE}/research/${item.id}`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("demo-notice")).toContainText(/ricerca reale/i);
  });
});
