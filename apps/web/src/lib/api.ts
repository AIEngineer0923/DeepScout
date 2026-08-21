import type { Overview, Workspace } from "./types";

export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parse<T>(responsePromise: Promise<Response>): Promise<T> {
  const response = await responsePromise;
  if (!response.ok) {
    const text = await response.text();
    let message = text || `Request failed (${response.status})`;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (typeof parsed.detail === "string" && parsed.detail) message = parsed.detail;
    } catch {
      /* keep raw text */
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const api = {
  overview: () => parse<Overview>(fetch(`${apiUrl}/api/v1/overview`, { cache: "no-store" })),
  settings: () => parse<Record<string, unknown>>(fetch(`${apiUrl}/api/v1/settings`, { cache: "no-store" })),
  listRuns: (params: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return parse<{ items: Overview["recent"]; total: number; limit: number; offset: number }>(
      fetch(`${apiUrl}/api/v1/research-runs?${query}`, { cache: "no-store" }),
    );
  },
  historyCsvUrl: (params: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams({ format: "csv", limit: "100" });
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return `${apiUrl}/api/v1/research-runs?${query}`;
  },
  createRun: (body: { goal: string; research_mode?: string; output_language?: string }) =>
    parse<{ id: string; research_mode?: string; output_language?: string }>(
      fetch(`${apiUrl}/api/v1/research-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  execute: (runId: string) =>
    parse<{ run_id: string; job_id: string }>(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/execute`, { method: "POST" }),
    ),
  cancel: (runId: string) =>
    parse(fetch(`${apiUrl}/api/v1/research-runs/${runId}/cancel`, { method: "POST" })),
  resume: (runId: string) =>
    parse<{ run_id: string }>(fetch(`${apiUrl}/api/v1/research-runs/${runId}/resume`, { method: "POST" })),
  restart: (runId: string) =>
    parse<{ run_id: string }>(fetch(`${apiUrl}/api/v1/research-runs/${runId}/restart`, { method: "POST" })),
  listReviews: (status = "pending") =>
    parse<Record<string, unknown>[]>(
      fetch(`${apiUrl}/api/v1/reviews?status=${encodeURIComponent(status)}`, { cache: "no-store" }),
    ),
  listRunReviews: (runId: string) =>
    parse<Record<string, unknown>[]>(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews`, { cache: "no-store" }),
    ),
  approveReview: (runId: string, reviewId: string, body: { reason?: string } = {}) =>
    parse(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews/${reviewId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  editReview: (
    runId: string,
    reviewId: string,
    body: {
      requested_extra_iterations: number;
      requested_extra_tool_calls: number;
      requested_extra_sources: number;
      reason?: string;
    },
  ) =>
    parse(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews/${reviewId}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  rejectReview: (runId: string, reviewId: string, body: { outcome?: string; reason?: string } = {}) =>
    parse(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews/${reviewId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  submitFeedback: (runId: string, body: Record<string, unknown>) =>
    parse(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  workspace: (runId: string) =>
    parse<Workspace>(fetch(`${apiUrl}/api/v1/research-runs/${runId}/workspace`, { cache: "no-store" })),
  snapshot: (runId: string, snapshotId: string) =>
    parse<Record<string, unknown>>(
      fetch(`${apiUrl}/api/v1/research-runs/${runId}/snapshots/${snapshotId}`, { cache: "no-store" }),
    ),
  exportUrl: (runId: string, format: string, snapshotId?: string) => {
    const query = new URLSearchParams({ format });
    if (snapshotId) query.set("snapshot_id", snapshotId);
    return `${apiUrl}/api/v1/research-runs/${runId}/export?${query}`;
  },
};
