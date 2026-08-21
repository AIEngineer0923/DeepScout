import { describe, expect, it } from "vitest";
import { MESSAGES, translate } from "./messages";

describe("i18n", () => {
  it("defaults English and interpolates", () => {
    expect(translate("en", "nav.overview")).toBe("Overview");
    expect(translate("en", "history.showing", { shown: 2, total: 9 })).toBe("Showing 2 of 9");
  });

  it("renders Italian product chrome", () => {
    expect(translate("it", "nav.overview")).toBe("Panoramica");
    expect(translate("it", "nav.newResearch")).toBe("Nuova ricerca");
    expect(translate("it", "action.start")).toBe("Avvia ricerca");
  });

  it("falls back to English then the key", () => {
    expect(translate("it", "brand.name")).toBe("DeepScout");
    expect(translate("en", "missing.never.defined")).toBe("missing.never.defined");
  });

  it("keeps English and Italian key sets aligned", () => {
    const missingIt = Object.keys(MESSAGES.en).filter((key) => !(key in MESSAGES.it));
    const extraIt = Object.keys(MESSAGES.it).filter((key) => !(key in MESSAGES.en));
    expect(missingIt).toEqual([]);
    expect(extraIt).toEqual([]);
  });
});
