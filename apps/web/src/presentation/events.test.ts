import { describe, expect, it } from "vitest";
import { presentEvent, eventMatchesFilter } from "./events";

describe("presentEvent", () => {
  it("maps run.completed to human labels", () => {
    expect(presentEvent("run.completed", "en").label).toBe("Research completed");
    expect(presentEvent("run.completed", "it").label).toBe("Ricerca completata");
  });

  it("uses phase-specific labels", () => {
    expect(presentEvent("phase.started", "it", { phase: "planning" }).label).toBe(
      "Pianificazione avviata",
    );
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
});
