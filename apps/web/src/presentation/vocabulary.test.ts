import { describe, expect, it } from "vitest";
import { vocab } from "./vocabulary";

describe("vocabulary", () => {
  it("returns localized normal labels", () => {
    expect(vocab("worker", "en")).toBe("Research agent");
    expect(vocab("worker", "it")).toBe("Agente di ricerca");
  });

  it("can expose technical labels", () => {
    expect(vocab("snapshot", "en", "technical")).toBe("Snapshot");
  });
});
