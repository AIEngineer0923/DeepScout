import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_RUN_ID, overviewFixture, settingsFixture, workspaceFixture } from "./fixtures";

const FOLLOW_ID = "33333333-3333-4333-8333-333333333333";

async function mockProduct(page: Page) {
  await page.addInitScript(() => {
    document.documentElement.setAttribute("data-visual", "1");
    window.localStorage.setItem("deepscout.last_run_id", "11111111-1111-4111-8111-111111111111");
  });
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: { authenticated: true, mode: "local", hosted_auth_ready: true, id: "local", display_name: "Local workspace" },
    }),
  );
  await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/workspace`, async (route) => {
    await route.fulfill({
      json: {
        ...workspaceFixture,
        status: "completed",
        runtime: { parent_run_id: null, lineage_kind: "none", fork_reason: null, replans_used: 0 },
        source_preferences: [],
        sources: workspaceFixture.sources.map((item) => ({ ...item, preference: "normal" })),
      },
    });
  });
  await page.route(`**/api/v1/research-runs/${FOLLOW_ID}/workspace`, async (route) => {
    await route.fulfill({
      json: {
        ...workspaceFixture,
        run_id: FOLLOW_ID,
        goal: "Dig deeper into this claim.",
        runtime: { parent_run_id: FIXTURE_RUN_ID, lineage_kind: "followup", fork_reason: "followup", replans_used: 0 },
      },
    });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/events**`, async (route) => {
    await route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } });
  });
  await page.route(`**/api/v1/research-runs/${FOLLOW_ID}/events**`, async (route) => {
    await route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/follow-up`, async (route) => {
    await route.fulfill({ json: { run_id: FOLLOW_ID, status: "accepted" } });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/source-preferences**`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        json: {
          id: "44444444-4444-4444-8444-444444444444",
          research_run_id: FIXTURE_RUN_ID,
          action: "pin",
          identity_kind: "url",
          identity_value: "https://example.com/battery",
          reason: "",
          origin: "user",
          created_at: "2026-08-21T10:00:00.000Z",
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.route("**/api/v1/research-monitors**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        json: {
          id: "55555555-5555-4555-8555-555555555555",
          name: "Daily monitor",
          goal: "Track battery regs",
          enabled: true,
          status: "active",
          timezone: "UTC",
          schedule_kind: "daily",
          next_run_at: "2026-08-22T09:00:00.000Z",
          last_run_at: null,
          last_change_at: null,
          last_run_id: null,
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.route("**/api/v1/knowledge/runs", async (route) => {
    await route.fulfill({ json: [{ run_id: FIXTURE_RUN_ID, goal: workspaceFixture.goal, page_count: 1 }] });
  });
  await page.route("**/api/v1/knowledge/pages?**", async (route) => {
    await route.fulfill({
      json: [{ id: "66666666-6666-4666-8666-666666666666", title: "Run findings", slug: "run-findings", status: "active", page_type: "topic" }],
    });
  });
  await page.route("**/api/v1/knowledge/graph?**", async (route) => {
    await route.fulfill({ json: { nodes: [{ id: "s1", label: "LFP is used" }], edges: [] } });
  });
  await page.route("**/api/v1/knowledge/statements/**", async (route) => {
    await route.fulfill({
      json: {
        id: "s1",
        text: "LFP is used in stationary storage",
        status: "active",
        claim: { id: "c1", statement: "LFP is used in stationary storage" },
        provenance: [
          {
            evidence_id: "e1",
            quote: "LFP packs",
            snapshot_id: "99999999-9999-4999-8999-999999999999",
            source_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
            source_url: "https://example.com/battery",
            passage: "exact passage",
          },
        ],
        not_evidence: true,
      },
    });
  });
  await page.route(`**/api/v1/research-runs/${FIXTURE_RUN_ID}/diff/**`, async (route) => {
    await route.fulfill({
      json: {
        left: { id: FIXTURE_RUN_ID, goal: "A" },
        right: { id: FOLLOW_ID, goal: "B" },
        sources: { added: ["https://new.example"], removed: [], unchanged: [] },
        claims: { added: ["new claim"], removed: [], unchanged: 1 },
        usage: { left: { total_tokens: 10, cost_status: "unknown" }, right: { total_tokens: 12, cost_status: "unknown" } },
      },
    });
  });
  await page.route("**/api/v1/research-runs?**", async (route) => {
    await route.fulfill({ json: { items: overviewFixture.recent, total: 1, limit: 8, offset: 0 } });
  });
}

test.describe("product completion flows", () => {
  test("follow-up from final report", async ({ page }) => {
    await mockProduct(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/report`);
    await page.getByTestId("followup-input").fill("Dig deeper into this claim.");
    await page.getByTestId("followup-start").click();
    await expect(page).toHaveURL(new RegExp(`/research/${FOLLOW_ID}`));
  });

  test("follow-up report links to originating run", async ({ page }) => {
    await mockProduct(page);
    await page.goto(`/research/${FOLLOW_ID}/report`);
    await expect(page.getByText(/Follow-up research|Ricerca di follow-up/)).toBeVisible();
    await expect(page.getByRole("link", { name: /originating|report originale|Open originating/i })).toBeVisible();
  });

  test("pin source posts preference", async ({ page }) => {
    await mockProduct(page);
    await page.goto(`/research/${FIXTURE_RUN_ID}/sources`);
    const posted = page.waitForRequest(
      (req) => req.method() === "POST" && req.url().includes("source-preferences"),
    );
    await page.getByTestId("pin-source").click();
    const req = await posted;
    expect(JSON.parse(req.postData() || "{}").action).toBe("pin");
  });

  test("create monitor", async ({ page }) => {
    await mockProduct(page);
    await page.goto("/monitors");
    await page.getByPlaceholder(/Research goal|Obiettivo/).fill("Track battery regs");
    await expect(page.getByTestId("monitor-create")).toBeEnabled();
    await page.getByTestId("monitor-create").click();
    await expect(page.getByTestId("monitor-create")).toBeVisible();
  });

  test("compare runs UI", async ({ page }) => {
    await mockProduct(page);
    await page.goto(`/compare?left=${FIXTURE_RUN_ID}&right=${FOLLOW_ID}`);
    await page.getByTestId("compare-run").click();
    await expect(page.getByText("Added")).toBeVisible();
  });

  test("knowledge home lists compiled runs", async ({ page }) => {
    await mockProduct(page);
    await page.goto("/knowledge");
    await expect(page.getByText("Compiled knowledge is not primary evidence.")).toBeVisible();
    await expect(page.getByRole("link", { name: workspaceFixture.goal })).toBeVisible();
  });

  test("knowledge statement provenance drill-down", async ({ page }) => {
    await mockProduct(page);
    await page.goto(`/knowledge/${FIXTURE_RUN_ID}/statement/s1`);
    await expect(page.getByTestId("knowledge-not-evidence")).toBeVisible();
    await expect(page.getByTestId("knowledge-provenance")).toBeVisible();
    await expect(page.getByText("exact passage")).toBeVisible();
    await expect(page.getByTestId("knowledge-source-link")).toBeVisible();
  });

  test("mobile layout for new surfaces", async ({ page }) => {
    await mockProduct(page);
    await page.setViewportSize({ width: 390, height: 844 });
    for (const path of ["/knowledge", "/monitors", "/compare"]) {
      await page.goto(path);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, path).toBeLessThanOrEqual(1);
    }
  });
});
