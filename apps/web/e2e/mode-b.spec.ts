import { expect, test } from "@playwright/test";
import { overviewFixture, settingsFixture } from "./fixtures";

test.describe("mode B public surfaces", () => {
  test("login offers GitHub, Google, and demo", async ({ page }) => {
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({ json: { authenticated: false, mode: "hosted", hosted_auth_ready: true } }),
    );
    await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
    await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
    await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Welcome to Deep Scout" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Continue with GitHub/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Continue with Google/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Explore demo/ })).toBeVisible();
  });

  test("demo is read-only copy", async ({ page }) => {
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({ json: { authenticated: false, mode: "hosted", hosted_auth_ready: true } }),
    );
    await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: { ...overviewFixture, recent: [] } }));
    await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
    await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
    await page.goto("/demo");
    await expect(page.getByText(/No signup/)).toBeVisible();
    await expect(page.getByRole("link", { name: /Run your own research/ })).toBeVisible();
  });

  test("account secret fields stay password inputs", async ({ page }) => {
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({
        json: { authenticated: true, mode: "hosted", hosted_auth_ready: true, id: "1", display_name: "A" },
      }),
    );
    await page.route("**/api/v1/overview", async (route) => route.fulfill({ json: overviewFixture }));
    await page.route("**/api/v1/settings", async (route) => route.fulfill({ json: settingsFixture }));
    await page.route("**/api/v1/rum/vitals", async (route) => route.fulfill({ status: 204, body: "" }));
    await page.route("**/api/v1/account", async (route) =>
      route.fulfill({
        json: {
          privacy: "encrypted at rest",
          credentials: [{ provider: "google", configured: true, status: "configured" }],
        },
      }),
    );
    await page.goto("/account");
    const input = page.locator("#cred-google");
    await expect(input).toHaveAttribute("type", "password");
    await expect(page.getByText(/google —/i)).toBeVisible();
    await expect(page.locator("body")).not.toContainText("sk-");
  });
});
