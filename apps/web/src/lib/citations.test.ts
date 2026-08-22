import { describe, expect, it } from "vitest";
import { buildCitationMap, linkifyNumericCitations } from "./citations";

const sources = [
  {
    id: "source-a",
    title: "Official guidance",
    url: "https://example.com/official",
    domain: "example.com",
    source_type: "web",
    created_at: null,
    fetch_state: "fetched",
    snapshot_available: true,
    snapshot_id: "snap-a",
    claim_count: 1,
    evidence_count: 1,
    task_id: null,
    task_key: null,
    worker_index: null,
  },
  {
    id: "source-b",
    title: "Industry report",
    url: "https://example.com/report",
    domain: "example.com",
    source_type: "web",
    created_at: null,
    fetch_state: "fetched",
    snapshot_available: true,
    snapshot_id: "snap-b",
    claim_count: 1,
    evidence_count: 1,
    task_id: null,
    task_key: null,
    worker_index: null,
  },
];

describe("buildCitationMap", () => {
  it("maps bibliography entries by citation number", () => {
    const markdown = `Body [1] and [2].

## Sources Cited
- [1] Official guidance https://example.com/official
- [2] Industry report https://example.com/report`;
    const map = buildCitationMap(markdown, sources);
    expect(map[1]?.sourceId).toBe("source-a");
    expect(map[2]?.sourceId).toBe("source-b");
  });
});

describe("linkifyNumericCitations", () => {
  it("links numeric citations without touching code fences", () => {
    const markdown = "Claim [1].\n\n```\n[2]\n```";
    const linked = linkifyNumericCitations(markdown, "run-1", {
      1: { sourceId: "source-a", title: "Official guidance", url: "https://example.com/official" },
    });
    expect(linked).toContain("(/research/run-1/sources/source-a)");
    expect(linked).toContain("```\n[2]\n```");
  });
});
