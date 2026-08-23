import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { MESSAGES } from "./messages";

/**
 * Every enum value that reaches a <StatusBadge> needs a `status.*` label in
 * both locales — without one the badge falls back to the raw backend value
 * (`insufficient_evidence`), which is a presentation leak, not a label.
 */
const BADGE_ENUMS = [
  "ResearchRunStatus",
  "ResearchTaskStatus",
  "ClaimVerificationStatus",
  "ContradictionEvidenceStatus",
  "MonitorStatus",
  "ReviewRequestStatus",
  "WikiPageStatus",
  "WikiStatementStatus",
  "IndexingStatus",
  "ResearchQuestionStatus",
];

function runtimeStatusValues(): string[] {
  const script = `import deepscout_core.domain.enums as e
vals = set()
for name in ${JSON.stringify(BADGE_ENUMS)}:
    vals |= {m.value for m in getattr(e, name)}
print("\\n".join(sorted(vals)))`;
  const out = execFileSync("uv", ["run", "python", "-c", script], {
    cwd: new URL("../../../../", import.meta.url).pathname,
    encoding: "utf8",
  });
  return out.trim().split("\n").filter(Boolean);
}

describe("status label coverage", () => {
  it("labels every badge-rendered status in English and Italian", () => {
    const values = runtimeStatusValues();
    expect(values.length).toBeGreaterThan(20);
    const missing: string[] = [];
    for (const value of values) {
      for (const locale of ["en", "it"] as const) {
        if (!MESSAGES[locale][`status.${value}`]) missing.push(`${locale}:${value}`);
      }
    }
    expect(missing).toEqual([]);
  });
});
