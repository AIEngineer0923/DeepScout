import { describe, expect, it } from "vitest";
import { displayGoal, displayReport } from "./demo";
import type { Workspace } from "@/lib/types";

const workspace = {
  run_id: "abc",
  goal: "English goal",
  status: "completed",
  presentation: {
    locale: "it",
    goal: "Obiettivo italiano",
    report: {
      title: "Report IT",
      body_markdown: "# Report\n\nCorpo italiano",
      is_localized: true,
    },
  },
} as Workspace;

describe("demo presentation helpers", () => {
  it("prefers localized goal", () => {
    expect(displayGoal(workspace, "it")).toBe("Obiettivo italiano");
  });

  it("falls back to authoritative goal", () => {
    expect(displayGoal({ ...workspace, presentation: null }, "it")).toBe("English goal");
  });

  it("returns localized report body", () => {
    const report = displayReport(workspace);
    expect(report.body).toContain("Corpo italiano");
    expect(report.localized).toBe(true);
  });
});
