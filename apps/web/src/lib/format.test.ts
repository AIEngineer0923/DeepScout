import { describe, expect, it } from "vitest";
import { formatCost, formatTokens } from "./format";

describe("formatCost", () => {
  it("never renders missing cost as zero", () => {
    expect(formatCost(null, "unknown")).toBe("Unknown");
    expect(formatCost(undefined, "unknown")).toBe("Unknown");
    expect(formatCost(0.04, "estimated")).toBe("$0.04");
  });
});

describe("formatTokens", () => {
  it("keeps unknown distinct from zero", () => {
    expect(formatTokens(null)).toBe("Unknown");
    expect(formatTokens(0)).toBe("0");
  });
});
