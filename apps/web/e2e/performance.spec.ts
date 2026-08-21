import { expect, test } from "@playwright/test";

const PROFILES = [
  { name: "FAST_WIFI", download: 30_000_000, upload: 15_000_000, latency: 20, cpu: 1 },
  { name: "SLOW_WIFI", download: 1_500_000, upload: 750_000, latency: 80, cpu: 1 },
  { name: "3G", download: 400_000, upload: 200_000, latency: 300, cpu: 4 },
  { name: "4G", download: 4_000_000, upload: 1_000_000, latency: 70, cpu: 1 },
  { name: "5G", download: 20_000_000, upload: 10_000_000, latency: 30, cpu: 1 },
] as const;

test.describe("lab network matrix", () => {
  test("dashboard remains usable under throttled Chromium profiles", async ({ page, browserName }) => {
    test.skip(browserName !== "chromium", "CDP network emulation is Chromium-only");
    test.skip(!process.env.PERF_LAB, "PERF_LAB not set");
    test.setTimeout(180_000);
    const session = await page.context().newCDPSession(page);
    await session.send("Network.enable");
    const results: Array<{ name: string; visibleMs: number }> = [];
    for (const profile of PROFILES) {
      await session.send("Network.emulateNetworkConditions", {
        offline: false,
        downloadThroughput: profile.download,
        uploadThroughput: profile.upload,
        latency: profile.latency,
      });
      await session.send("Emulation.setCPUThrottlingRate", { rate: profile.cpu });
      const started = Date.now();
      await page.goto("/", { waitUntil: "domcontentloaded" });
      await expect(page.locator(".page-title, h1, #content").first()).toBeVisible({ timeout: 20_000 });
      results.push({ name: profile.name, visibleMs: Date.now() - started });
    }
    await session.send("Network.emulateNetworkConditions", {
      offline: false,
      downloadThroughput: -1,
      uploadThroughput: -1,
      latency: 0,
    });
    await session.send("Emulation.setCPUThrottlingRate", { rate: 1 });
    // Localhost 3G still has no WAN RTT; this is lab data, not field CWV.
    expect(results.find((item) => item.name === "FAST_WIFI")?.visibleMs ?? 9_999).toBeLessThan(2_500);
    expect(results.every((item) => item.visibleMs < 20_000)).toBeTruthy();
  });
});
