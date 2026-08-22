import { describe, expect, it } from "vitest";
import type { Workspace } from "@/lib/types";
import {
  presentWorkerCardTitle,
  presentWorkerSecondarySummary,
  textsAreEquivalent,
  truncatePresentationText,
} from "@/presentation/workers";

const workspace = {
  workers: [
    {
      worker_id: "w1",
      index: 1,
      display_name: "W1",
      assigned_task:
        "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a production knowledge assistant in 2026.",
      state: "completed",
    },
  ],
  presentation: {
    workers: {
      w1: {
        display_name: "Hybrid RAG comparison",
        assigned_task:
          "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a production knowledge assistant in 2026.",
      },
    },
  },
} as unknown as Workspace;

describe("worker presentation helpers", () => {
  it("truncates long titles without breaking words aggressively", () => {
    const title = truncatePresentationText("one two three four five six seven eight nine ten", 20);
    expect(title.endsWith("…")).toBe(true);
    expect(title.length).toBeLessThanOrEqual(21);
  });

  it("detects equivalent repeated objective text", () => {
    const text =
      "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a production knowledge assistant in 2026.";
    expect(textsAreEquivalent(text, text)).toBe(true);
    expect(textsAreEquivalent("Hybrid RAG comparison", text)).toBe(false);
  });

  it("prefers short display names for card titles", () => {
    expect(presentWorkerCardTitle(workspace, "w1", "en")).toBe("Hybrid RAG comparison");
  });

  it("shows secondary summary only when it adds information", () => {
    expect(presentWorkerSecondarySummary(workspace, "w1")).toContain("GraphRAG");
    const duplicateWorkspace = {
      ...workspace,
      presentation: {
        workers: {
          w1: {
            display_name: "Hybrid RAG comparison",
            assigned_task: "Hybrid RAG comparison",
          },
        },
      },
    } as unknown as Workspace;
    expect(presentWorkerSecondarySummary(duplicateWorkspace, "w1")).toBeNull();
  });
});
