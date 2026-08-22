import { expect, test, type Page } from "@playwright/test";
import { settingsFixture } from "./fixtures";
import {
  XSS_FIXTURE_RUN_ID,
  XSS_KNOWLEDGE_PAGE_ID,
  XSS_PAYLOADS,
  XSS_SNAPSHOT_ID,
  xssKnowledgePageFixture,
  xssSnapshotFixture,
  xssWorkspaceFixture,
} from "./fixtures/xss-fixture";

async function mockXssFixture(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("deepscout.last_run_id", "11111111-1111-4111-8111-111111111111");
  });
  await page.route("**/api/v1/auth/me", async (route) =>
    route.fulfill({
      json: { authenticated: false, mode: "hosted", hosted_auth_ready: true },
    }),
  );
  await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
  await page.route(`**/api/v1/research-runs/${XSS_FIXTURE_RUN_ID}/workspace`, async (route) =>
    route.fulfill({ json: xssWorkspaceFixture }),
  );
  await page.route(`**/api/v1/research-runs/${XSS_FIXTURE_RUN_ID}/events**`, async (route) =>
    route.fulfill({ status: 200, body: "", headers: { "content-type": "text/event-stream" } }),
  );
  await page.route(
    `**/api/v1/research-runs/${XSS_FIXTURE_RUN_ID}/snapshots/${XSS_SNAPSHOT_ID}`,
    async (route) => route.fulfill({ json: xssSnapshotFixture }),
  );
  await page.route(`**/api/v1/knowledge/pages/${XSS_KNOWLEDGE_PAGE_ID}`, async (route) =>
    route.fulfill({ json: xssKnowledgePageFixture }),
  );
}

async function assertInertPublicSurface(page: Page, expectedTexts: readonly string[] = XSS_PAYLOADS) {
  await expect(page.locator("a[href^='javascript:']")).toHaveCount(0);
  await expect(page.locator("[onerror]")).toHaveCount(0);
  await expect(page.locator("[onload]")).toHaveCount(0);
  await expect(page.locator('img[src="x"]')).toHaveCount(0);
  for (const payload of expectedTexts) {
    await expect(page.locator("body")).toContainText(payload);
  }
}

test.describe("stored public research XSS regression", () => {
  test.beforeEach(async ({ page }) => {
    page.on("dialog", (dialog) => {
      throw new Error(`Unexpected dialog: ${dialog.message()}`);
    });
    await mockXssFixture(page);
  });

  test("CSP remains intact on demo surfaces", async ({ page }) => {
    const response = await page.goto(`/research/${XSS_FIXTURE_RUN_ID}/report`);
    expect(response).not.toBeNull();
    const csp = response?.headers()["content-security-policy"] ?? "";
    expect(csp).toContain("script-src");
    expect(csp).toContain("default-src 'self'");
  });

  test("source title renders inert payloads", async ({ page }) => {
    await page.goto(`/research/${XSS_FIXTURE_RUN_ID}/sources`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 15_000 });
    await assertInertPublicSurface(page, [XSS_PAYLOADS[1], XSS_PAYLOADS[2]]);
  });

  test("claims and evidence quotes render inert payloads", async ({ page }) => {
    await page.goto(`/research/${XSS_FIXTURE_RUN_ID}/claims`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 15_000 });
    await assertInertPublicSurface(page, [XSS_PAYLOADS[0], XSS_PAYLOADS[3]]);
  });

  test("final report renders inert payloads", async ({ page }) => {
    await page.goto(`/research/${XSS_FIXTURE_RUN_ID}/report`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 15_000 });
    await assertInertPublicSurface(page);
    const html = await page.locator(".rich-content.report-body-selectable").innerHTML();
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
  });

  test("snapshot text renders inert payloads", async ({ page }) => {
    await page.goto(`/research/${XSS_FIXTURE_RUN_ID}/snapshots/${XSS_SNAPSHOT_ID}`);
    await expect(page.getByTestId("demo-shell")).toBeVisible({ timeout: 15_000 });
    await assertInertPublicSurface(page);
  });

  test("wiki page renders inert payloads", async ({ page }) => {
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({
        json: {
          authenticated: true,
          mode: "local",
          hosted_auth_ready: true,
          id: "local",
          display_name: "Local workspace",
        },
      }),
    );
    await page.goto(`/knowledge/${XSS_FIXTURE_RUN_ID}/page/${XSS_KNOWLEDGE_PAGE_ID}`);
    await expect(page.locator("h1.page-title")).toBeVisible({ timeout: 15_000 });
    await assertInertPublicSurface(page, [XSS_PAYLOADS[0], XSS_PAYLOADS[4]]);
    const html = await page.locator(".rich-content").innerHTML();
    expect(html).not.toContain("<svg");
  });
});
