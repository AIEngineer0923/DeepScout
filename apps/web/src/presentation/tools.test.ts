import { describe, expect, it } from "vitest";

import { presentToolList } from "./tools";

describe("presentToolList", () => {
  it("renders a safe fallback when a public projection omits tools", () => {
    expect(presentToolList(undefined, "en")).toBe("—");
  });
});
