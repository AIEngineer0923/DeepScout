import { expect, test } from "@playwright/test";

const runId = process.env.LIVE_RUN_ID;

test.describe("live persisted run", () => {
  test.skip(!runId, "LIVE_RUN_ID not set");

  test("provenance navigation loads real IDs", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/");
    await page.goto(`/research/${runId}`);
    await expect(page.locator(".page-title")).toBeVisible();
    for (const path of ["plan", "workers", "sources", "snapshots", "claims", "quality", "report", "evaluations"]) {
      await page.goto(`/research/${runId}/${path}`);
      await expect(page.locator("#content")).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Internal Server Error");
    }
    await page.goto(`/resume/${runId}`);
    await expect(page.getByRole("heading").first()).toBeVisible();
    await page.goto("/history");
    await expect(page.locator("table.data")).toBeVisible();
  });

  test("sidebar provenance clicks and exports", async ({ page }) => {
    test.setTimeout(120_000);
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto(`/research/${runId}`);
    await page.getByRole("link", { name: /Plan \/ DAG|Piano \/ DAG/ }).click();
    await expect(page).toHaveURL(/\/plan/);
    await page.getByRole("link", { name: /^Workers$|^Worker$/ }).first().click();
    await expect(page).toHaveURL(/\/workers/);
    await page.getByRole("link", { name: /Sources|Fonti/ }).first().click();
    await expect(page).toHaveURL(/\/sources/);
    const pdf = await page.request.get(`http://127.0.0.1:8000/api/v1/research-runs/${runId}/export?format=pdf`);
    expect(pdf.ok()).toBeTruthy();
    expect(pdf.headers()["content-type"]).toContain("pdf");
    const csv = await page.request.get(`http://127.0.0.1:8000/api/v1/research-runs/${runId}/export?format=evals-csv`);
    expect(csv.ok()).toBeTruthy();
    expect(errors.filter((item) => !item.includes("favicon") && !item.includes("EventSource"))).toEqual([]);
  });

  test("capture live product screens for reference comparison", async ({ page }) => {
    test.skip(!process.env.CAPTURE_UI, "CAPTURE_UI not set");
    test.setTimeout(120_000);
    const out = "/tmp/deepscout-visual";
    const { mkdirSync } = await import("node:fs");
    mkdirSync(out, { recursive: true });
    await page.setViewportSize({ width: 1440, height: 1024 });
    const routes: Array<[string, string]> = [
      ["01-dashboard", "/"],
      ["02-new-research", "/research/new"],
      ["03-live", `/research/${runId}`],
      ["04-plan", `/research/${runId}/plan`],
      ["05-workers", `/research/${runId}/workers`],
      ["06-sources", `/research/${runId}/sources`],
      ["07-snapshots", `/research/${runId}/snapshots`],
      ["08-claims", `/research/${runId}/claims`],
      ["09-quality", `/research/${runId}/quality`],
      ["10-report", `/research/${runId}/report`],
      ["11-evaluations", `/research/${runId}/evaluations`],
      ["12-history", "/history"],
      ["13-resume", `/resume/${runId}`],
      ["14-settings", "/settings"],
    ];
    for (const [name, path] of routes) {
      await page.goto(path);
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${out}/${name}.png`, fullPage: false });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/research/${runId}`);
    await page.screenshot({ path: `${out}/15-mobile-run.png`, fullPage: false });
  });
});
