import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

const REVIEW_ID = "14141414-1414-4141-8141-141414141414";
const FORK_ID = "15151515-1515-4151-8151-151515151515";

const reviewFixture = [
  {
    id: REVIEW_ID,
    research_run_id: FIXTURE_RUN_ID,
    reason_code: "budget_extension",
    risk_level: "high",
    title: "Extend research budget",
    explanation: "Tool-call budget reached. Model text cannot approve this action.",
    proposed_action_type: "extend_budget",
    proposed_action_payload: {
      requested_extra_iterations: 2,
      requested_extra_tool_calls: 10,
      requested_extra_sources: 4,
    },
    payload_hash: "abc",
    status: "pending",
    version: 1,
    created_at: "2026-08-21T10:04:00.000Z",
    expires_at: null,
  },
];

async function mockRuntime(page: Page, workspace = workspaceFixture) {
  await page.addInitScript(() => {
    document.documentElement.setAttribute("data-visual", "1");
    window.localStorage.setItem("deepscout.last_run_id", "11111111-1111-4111-8111-111111111111");
  });
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: { authenticated: true, mode: "local", hosted_auth_ready: true, id: "local", display_name: "Local workspace" },
    }),
  );
  await page.route("**/api/v1/overview", async (route) => {
    await route.fulfill({ json: overviewFixture });
  });
  await page.route("**/api/v1/settings", async (route) => {
    await route.fulfill({ json: settingsFixture });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) => {
    await route.fulfill({ json: workspace });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) => {
    await route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } });
  });
  await page.route("**/api/v1/reviews**", async (route) => {
    await route.fulfill({ json: reviewFixture });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/reviews**`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { applied: true, status: "approved" } });
      return;
    }
    await route.fulfill({ json: reviewFixture });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/fork`, async (route) => {
    await route.fulfill({ json: { run_id: FORK_ID } });
  });
  await page.route("**/api/v1/research-runs?**", async (route) => {
    await route.fulfill({ json: { items: overviewFixture.recent, total: 1, limit: 8, offset: 0 } });
  });
}

test.describe("runtime surfaces", () => {
  test("workers page shows skills and progress", async ({ page }) => {
    await mockRuntime(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/workers`);
    await expect(page.locator("#content")).toBeVisible();
    await expect(page.getByText("citation-audit")).toBeVisible();
    await expect(page.locator(".worker-detail").getByRole("heading", { name: "Compare energy density" })).toBeVisible();
  });

  test("history lists runs", async ({ page }) => {
    await mockRuntime(page);
    await page.goto("/history");
    await expect(page.locator("table.data")).toBeVisible();
    await expect(page.getByText("Compare NMC and LFP battery chemistries")).toBeVisible();
  });

  test("reviews page lists HITL budget extension", async ({ page }) => {
    await mockRuntime(page);
    await page.goto("/reviews");
    await expect(page.getByRole("heading", { name: "Reviews" })).toBeVisible();
    await expect(page.getByText("Extend research budget")).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeVisible();
  });

  test("paused resume shows waiting banner and fork", async ({ page }) => {
    const paused = {
      ...workspaceFixture,
      status: "paused",
      resume: { ...workspaceFixture.resume, resumable: false },
    };
    await mockRuntime(page, paused);
    await page.goto(`/resume/${FIXTURE_RUN_ID}`);
    await expect(page.getByRole("heading", { name: "Waiting for review" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Fork as new run" })).toBeVisible();
    await page.getByRole("button", { name: "Fork as new run" }).click();
    await expect(page).toHaveURL(new RegExp(`/research/${FORK_ID}`));
  });
});
