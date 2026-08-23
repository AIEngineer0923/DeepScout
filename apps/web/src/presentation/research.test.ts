import { describe, expect, it } from "vitest";
import type { Workspace } from "@/lib/types";
import { compactResearchTitle, displayResearchTitle, normalizeResearchText } from "./research";

const longGoal =
  "Analizza se l’estrazione commerciale di noduli polimetallici dai fondali oceanici, con particolare attenzione alla Clarion–Clipperton Zone, possa essere giustificata sulla base delle evidenze disponibili nel 2026. Voglio capire: * quali minerali vengono estratti; * quali impatti sono stati osservati.";

describe("research presentation", () => {
  it("turns a long prompt into a bounded editorial title", () => {
    const title = compactResearchTitle(longGoal);
    expect(title).toBe("Analizza se l’estrazione commerciale di noduli polimetallici dai fondali…");
    expect(title.length).toBeLessThanOrEqual(80);
  });

  it("keeps short goals unchanged and normalizes pasted markdown", () => {
    expect(compactResearchTitle("Compare NMC and LFP batteries")).toBe("Compare NMC and LFP batteries");
    expect(normalizeResearchText("# Research\n\n- Compare evidence")).toBe("Research Compare evidence");
  });

  it("prefers an explicit presentation title", () => {
    const workspace = {
      goal: longGoal,
      presentation: { locale: "it", goal: longGoal, title: "Noduli polimetallici nel 2026" },
      report: null,
    } as Workspace;
    expect(displayResearchTitle(workspace, "it")).toBe("Noduli polimetallici nel 2026");
  });

  it("does not replace the research identity with a generic report title", () => {
    const workspace = {
      goal: "Compare NMC and LFP batteries",
      presentation: null,
      report: { title: "Research Report" },
    } as Workspace;
    expect(displayResearchTitle(workspace, "en")).toBe("Compare NMC and LFP batteries");
  });
});
