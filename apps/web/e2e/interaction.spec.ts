import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

async function mockApi(page: Page) {
  await page.addInitScript(() => {
    document.documentElement.setAttribute("data-visual", "1");
    window.localStorage.setItem("deepscout.last_run_id", "11111111-1111-4111-8111-111111111111");
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
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) => {
    await route.fulfill({ json: workspaceFixture });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) => {
    await route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } });
  });
  await page.route("**/api/v1/research-templates**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        json: {
          id: "22222222-2222-4222-8222-222222222222",
          name: "Preset",
          goal: "Compare NMC and LFP",
          research_mode: "standard",
          output_language: "en",
          created_at: "2026-08-21T10:00:00.000Z",
          updated_at: "2026-08-21T10:00:00.000Z",
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.route("**/api/v1/research-runs?**", async (route) => {
    await route.fulfill({ json: { items: overviewFixture.recent, total: 0, limit: 8, offset: 0 } });
  });
}

test.describe("interaction", () => {
  test("sidebar navigates and disabled items go to select", async ({ page }) => {
    await mockApi(page);
    await page.goto("/dashboard");
    await page.getByLabel("Primary navigation").getByRole("link", { name: "New Research" }).click();
    await expect(page).toHaveURL(/\/research\/new/);
    await page.getByLabel("Primary navigation").getByRole("link", { name: "Live Research" }).click();
    await expect(page).toHaveURL(new RegExp(`/research/${FIXTURE_RUN_ID}`));
    await page.getByLabel("Primary navigation").getByRole("link", { name: "Plan / DAG" }).click();
    await expect(page).toHaveURL(/\/plan/);
    await page.getByLabel("Primary navigation").getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL(/\/settings/);
  });

  test("research mode switches visually", async ({ page }) => {
    await mockApi(page);
    await page.goto("/research/new");
    await page.getByTestId("mode-quick").click();
    await expect(page.getByTestId("mode-quick")).toHaveClass(/selected/);
    await expect(page.getByTestId("summary-mode")).toHaveAttribute("data-value", "quick");
    await page.getByTestId("mode-deep").click();
    await expect(page.getByTestId("mode-deep")).toHaveClass(/selected/);
    await expect(page.getByTestId("summary-mode")).toHaveAttribute("data-value", "deep");
    await page.getByTestId("mode-standard").click();
    await expect(page.getByTestId("summary-mode")).toHaveAttribute("data-value", "standard");
  });

  test("settings tabs switch content", async ({ page }) => {
    await mockApi(page);
    await page.goto("/settings");
    await page.getByRole("tab", { name: "Models & Providers" }).click();
    await expect(page.getByText("API keys are never displayed.")).toBeVisible();
    await page.getByRole("tab", { name: "General" }).click();
    await expect(page.getByTestId("settings-ui-language")).toBeVisible();
  });

  test("Italian UI persists after reload", async ({ page }) => {
    await mockApi(page);
    await page.goto("/dashboard");
    await page.getByTestId("ui-lang-it").click();
    await expect(page.getByRole("link", { name: "Panoramica" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("link", { name: "Panoramica" })).toBeVisible();
    await page.getByRole("link", { name: "Nuova ricerca" }).click();
    await expect(page.getByRole("heading", { name: "Nuova ricerca" })).toBeVisible();
    await expect(page.getByTestId("output-language")).toBeVisible();
  });

  test("UI Italian keeps research output English and Deep in the payload", async ({ page }) => {
    await mockApi(page);
    let body: Record<string, unknown> | null = null;
    await page.route("**/api/v1/research-runs", async (route) => {
      if (route.request().method() === "POST") {
        body = route.request().postDataJSON() as Record<string, unknown>;
        await route.fulfill({ json: { id: FIXTURE_RUN_ID, research_mode: body.research_mode, output_language: body.output_language } });
        return;
      }
      await route.continue();
    });
    await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/execute`, async (route) => {
      await route.fulfill({ json: { run_id: FIXTURE_RUN_ID, job_id: FIXTURE_RUN_ID } });
    });
    await page.goto("/research/new");
    await page.getByTestId("ui-lang-it").click();
    await page.getByTestId("research-goal").fill("Compare EU AI Act obligations for a SaaS vendor.");
    await page.getByTestId("mode-deep").click();
    await page.getByTestId("output-language").selectOption("en");
    await page.getByTestId("start-research").click();
    await expect.poll(() => body).not.toBeNull();
    expect(body).toMatchObject({ research_mode: "deep", output_language: "en" });
    await expect(page.getByRole("link", { name: "Nuova ricerca" })).toBeVisible();
  });

  test("new research filters are enabled and configurable", async ({ page }) => {
    await mockApi(page);
    await page.goto("/research/new");
    await expect(page.locator("#freshness")).toBeEnabled();
    await expect(page.locator("#geo-mode")).toBeEnabled();
    await page.getByTestId("geo-mode").selectOption("regions");
    await page.getByRole("button", { name: "Italy" }).click();
    await page.getByRole("button", { name: "Show advanced settings" }).click();
    await expect(page.locator("#excluded")).toBeEnabled();
  });

  test("workspace tabs navigate provenance routes", async ({ page }) => {
    await mockApi(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}`);
    await page.getByRole("navigation", { name: "Research" }).getByRole("link", { name: "Workers" }).click();
    await expect(page).toHaveURL(/\/workers/);
    await page.getByRole("navigation", { name: "Research" }).getByRole("link", { name: "Snapshot" }).click();
    await expect(page).toHaveURL(/\/snapshots/);
    await page.getByRole("navigation", { name: "Research" }).getByRole("link", { name: "Report" }).click();
    await expect(page).toHaveURL(/\/report/);
  });

  test("history tabs filter and pagination controls exist", async ({ page }) => {
    await mockApi(page);
    await page.goto("/history");
    await page.getByRole("tab", { name: "Completed" }).click();
    await expect(page.getByRole("tab", { name: "Completed" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  test("new research can save and apply a template", async ({ page }) => {
    await mockApi(page);
    const saved: Array<Record<string, unknown>> = [];
    await page.route("**/api/v1/research-templates**", async (route) => {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON() as Record<string, unknown>;
        saved.push(body);
        await route.fulfill({
          status: 201,
          json: {
            id: "22222222-2222-4222-8222-222222222222",
            name: body.name,
            goal: body.goal,
            research_mode: body.research_mode,
            output_language: body.output_language,
            created_at: "2026-08-21T10:00:00.000Z",
            updated_at: "2026-08-21T10:00:00.000Z",
          },
        });
        return;
      }
      await route.fulfill({
        json: saved.map((item, index) => ({
          id: "22222222-2222-4222-8222-222222222222",
          name: item.name,
          goal: item.goal,
          research_mode: item.research_mode,
          output_language: item.output_language,
          created_at: "2026-08-21T10:00:00.000Z",
          updated_at: "2026-08-21T10:00:00.000Z",
          _i: index,
        })),
      });
    });
    await page.goto("/research/new");
    await expect(page.getByRole("heading", { name: "New Research" })).toBeVisible();
    const goal = page.getByTestId("research-goal");
    await goal.click();
    await goal.fill("Name two common EV battery chemistries.");
    await expect(goal).toHaveValue("Name two common EV battery chemistries.");
    await page.getByRole("button", { name: "Save as template" }).click();
    await page.getByTestId("template-name").fill("Battery lookup");
    await page.getByTestId("save-template").click();
    await expect(page.getByText("Template saved")).toBeVisible();
    await expect(page.getByTestId("template-list")).toContainText("Battery lookup");
    await goal.fill("");
    await expect(goal).toHaveValue("");
    await page.getByTestId("apply-template-22222222-2222-4222-8222-222222222222").click();
    await expect(goal).toHaveValue("Name two common EV battery chemistries.");
  });
});
