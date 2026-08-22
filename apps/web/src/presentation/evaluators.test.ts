import { describe, expect, it } from "vitest";
import {
  FORBIDDEN_UI_PATTERNS,
  presentEvaluator,
  presentEvaluatorResult,
} from "./evaluators";

describe("evaluators presentation", () => {
  it("humanizes claim_has_evidence", () => {
    const presented = presentEvaluator("claim_has_evidence", "en");
    expect(presented.title).toBe("Claim coverage");
    expect(presented.description).toMatch(/verified claim/i);
  });

  it("maps boolean pass/fail", () => {
    expect(presentEvaluatorResult("claim_has_evidence", true, "en")).toBe("Passed");
    expect(presentEvaluatorResult("claim_has_evidence", false, "it")).toBe("Non superato");
  });

  it("does not expose raw evaluator ids in titles", () => {
    for (const id of ["claim_has_evidence", "citation_correctness", "ragas_faithfulness"]) {
      const title = presentEvaluator(id, "en").title;
      expect(title).not.toContain(id);
    }
  });
});

describe("forbidden leak patterns", () => {
  it("lists representative internal strings", () => {
    expect(FORBIDDEN_UI_PATTERNS).toContain("run.completed");
    expect(FORBIDDEN_UI_PATTERNS).toContain("text/html; charset");
  });
});
