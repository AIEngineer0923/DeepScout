import { describe, expect, it } from "vitest";
import { elapsed, formatCost, formatDuration, formatTokens } from "./format";

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

describe("run timing", () => {
  it("reads a finished run as a duration, not a running stopwatch", () => {
    const start = "2026-08-01T10:00:00Z";
    expect(formatDuration(start, "2026-08-01T10:12:30Z")).toBe("12 min 30 s");
    expect(formatDuration(start, "2026-08-01T11:05:00Z")).toBe("1 h 5 min");
    expect(formatDuration(start, "2026-08-01T10:00:42Z")).toBe("42 s");
    expect(formatDuration(start, null)).toBe("—");
  });

  it("rolls the stopwatch over to hours instead of counting past 60 minutes", () => {
    expect(elapsed("2026-08-01T10:00:00Z", "2026-08-01T10:09:11Z")).toBe("09:11");
    expect(elapsed("2026-08-01T10:00:00Z", "2026-08-02T02:30:54Z")).toBe("16:30:54");
  });
});
