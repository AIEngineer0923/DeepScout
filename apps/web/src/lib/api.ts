import type { Overview, Workspace } from "./types";

export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parse<T>(responsePromise: Promise<Response>): Promise<T> {
  const response = await responsePromise;
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
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
  createRun: (body: { goal: string; research_mode?: string }) =>
    parse<{ id: string }>(
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
