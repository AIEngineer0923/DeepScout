import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

test("core screens have no serious axe violations", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("deepscout.last_run_id", "11111111-1111-4111-8111-111111111111");
  });
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) =>
    route.fulfill({ json: workspaceFixture }),
  );
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) =>
    route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } }),
  );
  for (const path of ["/", "/research/new", `/research/${FIXTURE_RUN_ID}`, "/settings", "/history"]) {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    const serious = results.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
    expect(serious, path).toEqual([]);
  }
});
