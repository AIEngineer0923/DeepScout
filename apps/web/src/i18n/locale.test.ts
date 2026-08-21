import { describe, expect, it } from "vitest";
import { detectLocaleFromAcceptLanguage, detectLocaleFromNavigator } from "./locale";

describe("locale detection", () => {
  it("maps Italy Accept-Language to Italian", () => {
    expect(detectLocaleFromAcceptLanguage("it-IT,it;q=0.9,en;q=0.8")).toBe("it");
    expect(detectLocaleFromAcceptLanguage("en-IT,en;q=0.9")).toBe("it");
  });

  it("maps non-Italy Accept-Language to English", () => {
    expect(detectLocaleFromAcceptLanguage("en-US,en;q=0.9")).toBe("en");
    expect(detectLocaleFromAcceptLanguage("de-DE,de;q=0.9")).toBe("en");
  });

  it("maps navigator Italy signals to Italian", () => {
    const original = global.navigator;
    Object.defineProperty(global, "navigator", {
      configurable: true,
      value: { language: "it-IT", languages: ["it-IT", "it"] },
    });
    expect(detectLocaleFromNavigator()).toBe("it");
    Object.defineProperty(global, "navigator", { configurable: true, value: original });
  });
});
