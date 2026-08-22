import { describe, expect, it } from "vitest";
import {
  eventMatchesFilter,
  presentEvent,
  timelineDedupKey,
} from "./events";

describe("presentEvent", () => {
  it("maps run.completed to human labels", () => {
    expect(presentEvent("run.completed", "en").label).toBe("Research completed");
    expect(presentEvent("run.completed", "it").label).toBe("Ricerca completata");
  });

  it("uses runtime phase labels", () => {
    expect(presentEvent("phase.started", "it", { phase: "plan" }).label).toBe("Pianificazione avviata");
    expect(presentEvent("phase.started", "en", { phase: "verify" }).label).toBe("Verification started");
  });

  it("shows source hostname in detail", () => {
    const detail = presentEvent("source.discovered", "en", {
      url: "https://example.com/path",
      worker_id: "W01",
    }).detail;
    expect(detail).toContain("example.com");
  });

  it("never returns raw event codes for known events", () => {
    const label = presentEvent("source.discovered", "en").label;
    expect(label).not.toContain("source.discovered");
  });

  it("falls back to readable generic label for unknown events", () => {
    expect(presentEvent("foo.bar.baz", "en").label).toContain("Event:");
  });
});

describe("eventMatchesFilter", () => {
  it("filters worker events", () => {
    expect(eventMatchesFilter("worker.started", "worker")).toBe(true);
    expect(eventMatchesFilter("source.discovered", "worker")).toBe(false);
  });

  it("routes verify phase events to quality filter", () => {
    expect(eventMatchesFilter("phase.completed", "quality", { phase: "verify" })).toBe(true);
    expect(eventMatchesFilter("phase.completed", "phase", { phase: "verify" })).toBe(false);
  });

  it("routes extract phase events to evidence filter", () => {
    expect(eventMatchesFilter("phase.started", "evidence", { phase: "extract" })).toBe(true);
  });

  it("routes report phase events to report filter", () => {
    expect(eventMatchesFilter("phase.completed", "report", { phase: "report" })).toBe(true);
  });
});

describe("timelineDedupKey", () => {
  it("keeps distinct source URLs separate", () => {
    const a = timelineDedupKey("source.discovered", { url: "https://a.example" });
    const b = timelineDedupKey("source.discovered", { url: "https://b.example" });
    expect(a).not.toBe(b);
  });
});
