import { describe, expect, it } from "vitest";
import { truncateMarkdownBody } from "./markdown";

describe("truncateMarkdownBody", () => {
  it("keeps short bodies intact", () => {
    expect(truncateMarkdownBody("Short report", 100)).toEqual({
      body: "Short report",
      truncated: false,
    });
  });

  it("truncates at paragraph boundaries when possible", () => {
    const body = "Paragraph one.\n\nParagraph two with more detail.";
    const result = truncateMarkdownBody(body, 20);
    expect(result.truncated).toBe(true);
    expect(result.body).toBe("Paragraph one.");
  });
});
