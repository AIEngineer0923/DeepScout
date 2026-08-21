import { describe, expect, it } from "vitest";
import { safeHttpUrl } from "./safe-url";

describe("safeHttpUrl", () => {
  it("allows https", () => {
    expect(safeHttpUrl("https://example.com/a")).toBe("https://example.com/a");
  });

  it("rejects javascript and data URLs", () => {
    expect(safeHttpUrl("javascript:alert(1)")).toBeNull();
    expect(safeHttpUrl("data:text/html,<script>x</script>")).toBeNull();
  });
});
