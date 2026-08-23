import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

const LONG_GOAL =
  "Analizza se l’estrazione commerciale di noduli polimetallici dai fondali oceanici, con particolare attenzione alla Clarion–Clipperton Zone, possa essere giustificata sulla base delle evidenze disponibili nel 2026. Voglio capire: * quali minerali vengono estratti dai noduli; * quali tecnologie vengono proposte; * quali impatti ambientali sono stati osservati; * quali risultati quantitativi esistono; * quali questioni scientifiche devono ancora essere risolte.";

const EXPECTED_TITLE =
  "Analizza se l’estrazione commerciale di noduli polimetallici dai fondali…";

async function mockLongResearch(page: Page) {
  const workspace = { ...workspaceFixture, goal: LONG_GOAL, report: null };
  await page.addInitScript(() => {
    window.localStorage.setItem("deepscout.ui_locale", "it");
    document.cookie = "deepscout.ui_locale=it; path=/";
  });
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: { authenticated: true, mode: "local", hosted_auth_ready: true, id: "local", display_name: "Local workspace" },
    }),
  );
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace**`, async (route) =>
    route.fulfill({ json: workspace }),
  );
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) =>
    route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } }),
  );
}

test("long research requests stay compact and accessible at every viewport", async ({ page }) => {
  await mockLongResearch(page);

  for (const width of [320, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`/research/${FIXTURE_RUN_ID}/report`);

    const title = page.getByTestId("research-title");
    await expect(title).toHaveText(EXPECTED_TITLE);
    await expect(page.getByTestId("research-goal-details")).toHaveCount(0);
    expect((await title.boundingBox())?.height ?? 999, `title height at ${width}px`).toBeLessThan(90);

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(1);
    if (width <= 390) {
      expect((await page.locator(".research-header").boundingBox())?.height ?? 999).toBeLessThan(550);
    }
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/research/${FIXTURE_RUN_ID}/report`);
  await expect(page.getByTestId("research-title")).toHaveText(EXPECTED_TITLE);
  const toggle = page.locator(".research-goal-toggle");
  await expect(toggle).toHaveAccessibleName("Mostra richiesta completa");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(toggle).toHaveAccessibleName("Nascondi richiesta completa");
  await expect(page.getByTestId("research-goal-details")).toContainText(LONG_GOAL);
  expect((await page.getByTestId("research-goal-details").boundingBox())?.height ?? 999).toBeLessThan(300);
});

test("the compact mobile live view uses the same bounded title", async ({ page }) => {
  await mockLongResearch(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/research/${FIXTURE_RUN_ID}`);
  const mobileTitle = page.locator(".live-mobile").getByTestId("research-title");
  await expect(mobileTitle).toHaveText(EXPECTED_TITLE);
  expect((await mobileTitle.boundingBox())?.height ?? 999).toBeLessThan(90);
});
