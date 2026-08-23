import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

const LONG_GOAL =
  "Analizza se l’estrazione commerciale di noduli polimetallici dai fondali oceanici, con particolare attenzione alla Clarion–Clipperton Zone, possa essere giustificata sulla base delle evidenze disponibili nel 2026. Voglio capire: * quali minerali vengono estratti dai noduli; * quali tecnologie vengono proposte; * quali impatti ambientali sono stati osservati; * quali risultati quantitativi esistono; * quali questioni scientifiche devono ancora essere risolte.";

const EXPECTED_TITLE =
  "Analizza se l’estrazione commerciale di noduli polimetallici dai fondali…";

const LONG_TASK =
  "Confronta in modo sistematico tutte le architetture richieste, valuta qualità del recupero, provenienza, costi, sicurezza, latenza, complessità operativa e casi d’uso, riportando ogni limite metodologico e ogni fonte primaria disponibile.";
const LONG_SOURCE_TITLE =
  "A comprehensive systematic review of hybrid retrieval augmented generation architectures, operational trade-offs, provenance, security, latency and evaluation strategies";

function longWorkspace() {
  return {
    ...workspaceFixture,
    goal: LONG_GOAL,
    tasks: workspaceFixture.tasks.map((task) => ({ ...task, objective: LONG_TASK })),
    workers: workspaceFixture.workers.map((worker) => ({
      ...worker,
      display_name: `W${worker.index.toString().padStart(2, "0")} · ${LONG_TASK}`,
      assigned_task: LONG_TASK,
    })),
    sources: workspaceFixture.sources.map((source) => ({ ...source, title: LONG_SOURCE_TITLE })),
    report: workspaceFixture.report ? { ...workspaceFixture.report, title: LONG_TASK } : null,
  };
}

async function mockLongResearch(page: Page, demo = false) {
  const workspace = longWorkspace();
  await page.addInitScript(() => {
    window.localStorage.setItem("deepscout.ui_locale", "it");
    document.cookie = "deepscout.ui_locale=it; path=/";
  });
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: demo
        ? { authenticated: false, mode: "hosted", hosted_auth_ready: true }
        : { authenticated: true, mode: "local", hosted_auth_ready: true, id: "local", display_name: "Local workspace" },
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
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto(`/research/${FIXTURE_RUN_ID}/report`);

  for (const width of [320, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });

    const title = page.getByTestId("research-title");
    await expect(title).toHaveText(EXPECTED_TITLE);
    await expect(page.getByTestId("research-goal-details")).toHaveCount(0);
    expect((await title.boundingBox())?.height ?? 999, `title height at ${width}px`).toBeLessThan(90);

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(1);
    if (width <= 390) {
      const flexBasis = await page
        .locator(".research-header-copy")
        .evaluate((element) => window.getComputedStyle(element).flexBasis);
      expect(flexBasis).toBe("auto");
    }
  }

  await page.setViewportSize({ width: 390, height: 844 });
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

test("public demo modules bound all generated titles and objectives", async ({ page, browserName }) => {
  test.skip(browserName !== "chromium", "One engine is sufficient for the cross-module presentation audit");
  await mockLongResearch(page, true);
  await page.setViewportSize({ width: 1440, height: 1000 });

  const modules = [
    { path: "plan", selector: ".task-item .clamped-text-3", clamp: "3", container: ".task-item", maxHeight: 230 },
    { path: "workers", selector: ".worker-card-title", clamp: "2", container: ".worker-card", maxHeight: 240 },
    { path: "sources", selector: ".data .clamped-text-2", clamp: "2", container: ".data tbody tr", maxHeight: 130 },
    { path: "report", selector: ".report-document .generated-heading", clamp: "3", container: ".report-document .generated-heading", maxHeight: 100 },
  ];

  for (const module of modules) {
    await page.goto(`/research/${FIXTURE_RUN_ID}/${module.path}`);
    await expect(page.getByTestId("demo-shell")).toBeVisible();
    await expect(page.getByTestId("research-title")).toHaveText(EXPECTED_TITLE);
    const generated = page.locator(module.selector).first();
    await expect(generated).toBeVisible();
    const lineClamp = await generated.evaluate(
      (element) => window.getComputedStyle(element).webkitLineClamp,
    );
    expect(lineClamp, `${module.path} line clamp`).toBe(module.clamp);
    const maxContainerHeight = await page.locator(module.container).evaluateAll((elements) =>
      Math.max(...elements.map((element) => element.getBoundingClientRect().height)),
    );
    expect(maxContainerHeight, `${module.path} generated content height`).toBeLessThan(module.maxHeight);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `${module.path} horizontal overflow`).toBeLessThanOrEqual(1);
  }
});
