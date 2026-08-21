import { describe, expect, it } from "vitest";
import { isDemoRunPath, isPublicEntryPath, parseRunIdFromPath } from "./routing";

const RUN_ID = "11111111-1111-4111-8111-111111111111";

describe("routing", () => {
  it("classifies public entry paths", () => {
    expect(isPublicEntryPath("/")).toBe(true);
    expect(isPublicEntryPath("/demo")).toBe(true);
    expect(isPublicEntryPath("/login")).toBe(true);
    expect(isPublicEntryPath("/dashboard")).toBe(false);
  });

  it("classifies demo run paths", () => {
    expect(isDemoRunPath(`/research/${RUN_ID}`)).toBe(true);
    expect(isDemoRunPath(`/research/${RUN_ID}/report`)).toBe(true);
    expect(isDemoRunPath("/research/new")).toBe(false);
    expect(isDemoRunPath("/dashboard")).toBe(false);
  });

  it("parses run id from path", () => {
    expect(parseRunIdFromPath(`/research/${RUN_ID}/plan`)).toBe(RUN_ID);
    expect(parseRunIdFromPath("/research/new")).toBeNull();
  });
});
