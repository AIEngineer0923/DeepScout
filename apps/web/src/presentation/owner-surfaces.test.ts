import { describe, expect, it } from "vitest";
import { presentMonitorStatus, presentScheduleKind } from "./monitors";
import { presentKnowledgePageType, presentKnowledgeRelation } from "./knowledge";
import { presentToolName } from "./tools";

describe("monitor presentation", () => {
  it("humanizes monitor status", () => {
    expect(presentMonitorStatus("waiting_for_review", "it")).toBe("In attesa di revisione");
    expect(presentMonitorStatus("active", "en")).toBe("Active");
  });

  it("humanizes schedule kind", () => {
    expect(presentScheduleKind("daily", "it")).toBe("Giornaliero");
  });
});

describe("knowledge presentation", () => {
  it("humanizes page types and relations", () => {
    expect(presentKnowledgePageType("finding", "en")).toBe("Finding page");
    expect(presentKnowledgeRelation("supports", "it")).toBe("Supporta");
    expect(presentKnowledgeRelation("REFUTES", "en")).toBe("Refutes");
  });
});

describe("tool presentation", () => {
  it("humanizes tool identifiers", () => {
    expect(presentToolName("web_search", "en")).toBe("Web search");
    expect(presentToolName("citation_audit", "it")).toBe("Verifica citazioni");
  });
});
