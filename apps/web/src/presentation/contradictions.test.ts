import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  CONTRADICTION_KINDS,
  contradictionKindLabel,
  presentContradiction,
} from "./contradictions";

const RUNTIME_SOURCE = new URL(
  "../../../../libs/research/src/deepscout_research/phases/contradiction.py",
  import.meta.url,
);

describe("contradiction presentation", () => {
  it("covers exactly the kinds the research runtime emits", () => {
    const python = readFileSync(RUNTIME_SOURCE, "utf8");
    const block = python.match(/CONTRADICTION_KINDS: tuple\[str, \.\.\.\] = \(([\s\S]*?)\)/);
    expect(block).not.toBeNull();
    const runtimeKinds = [...block![1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    expect(runtimeKinds).toEqual([...CONTRADICTION_KINDS]);
  });

  it("localizes each kind and detail shape into Italian", () => {
    const samples = [
      "Timeframe difference: only one claim is scoped to 2025",
      "Scope difference: only one claim is scoped to europe",
      "Methodological difference: the claims differ on recycling",
      "Negation conflict: one claim asserts what the other denies",
      "Opposing values: lower versus higher on a comparable proposition",
    ];
    for (const sample of samples) {
      const italian = presentContradiction(sample, "it");
      expect(italian).not.toEqual(sample);
      expect(italian).not.toMatch(/only one claim|the claims differ|asserts what|comparable proposition/);
    }
  });

  it("passes English through unchanged and leaves unknown shapes alone", () => {
    const english = "Timeframe difference: only one claim is scoped to 2025";
    expect(presentContradiction(english, "en")).toBe(english);
    expect(presentContradiction("something else entirely", "it")).toBe("something else entirely");
    expect(contradictionKindLabel("something else entirely", "it")).toBeNull();
    expect(contradictionKindLabel(english, "it")).toBe("Differenza temporale");
  });
});
