import type { Overview, Workspace } from "./types";

export const apiUrl =
  process.env.NEXT_PUBLIC_API_URL !== undefined
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")
    : process.env.NODE_ENV === "production"
      ? ""
      : "http://localhost:8000";

function apiFetch(url: string, init: RequestInit = {}) {
  return fetch(url, { credentials: "include", cache: "no-store", ...init });
}

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
  overview: () => parse<Overview>(apiFetch(`${apiUrl}/api/v1/overview`, { cache: "no-store" })),
  me: () =>
    parse<{
      authenticated: boolean;
      mode: string;
      hosted_auth_ready: boolean;
      id?: string;
      display_name?: string;
      kind?: string;
    }>(apiFetch(`${apiUrl}/api/v1/auth/me`)),
  account: () => parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/account`)),
  saveCredential: (provider: string, secret: string) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/account/credentials/${provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      }),
    ),
  logout: () => parse(apiFetch(`${apiUrl}/api/v1/auth/logout`, { method: "POST" })),
  logoutAll: () => parse(apiFetch(`${apiUrl}/api/v1/auth/logout-all`, { method: "POST" })),
  exportAccount: () => parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/account/export`)),
  deleteAccount: () => parse(apiFetch(`${apiUrl}/api/v1/account/delete`, { method: "POST" })),
  settings: () => parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/settings`, { cache: "no-store" })),
  listRuns: (params: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return parse<{ items: Overview["recent"]; total: number; limit: number; offset: number }>(
      apiFetch(`${apiUrl}/api/v1/research-runs?${query}`, { cache: "no-store" }),
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
      apiFetch(`${apiUrl}/api/v1/research-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  execute: (runId: string) =>
    parse<{ run_id: string; job_id: string }>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/execute`, { method: "POST" }),
    ),
  cancel: (runId: string) =>
    parse(apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/cancel`, { method: "POST" })),
  resume: (runId: string) =>
    parse<{ run_id: string }>(apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/resume`, { method: "POST" })),
  restart: (runId: string) =>
    parse<{ run_id: string }>(apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/restart`, { method: "POST" })),
  fork: (runId: string, reason = "operator_fork") =>
    parse<{ run_id: string }>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/fork`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      }),
    ),
  listReviews: (status = "pending") =>
    parse<Record<string, unknown>[]>(
      apiFetch(`${apiUrl}/api/v1/reviews?status=${encodeURIComponent(status)}`, { cache: "no-store" }),
    ),
  listRunReviews: (runId: string) =>
    parse<Record<string, unknown>[]>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews`, { cache: "no-store" }),
    ),
  approveReview: (runId: string, reviewId: string, body: { reason?: string } = {}) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews/${reviewId}/approve`, {
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
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews/${reviewId}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  rejectReview: (runId: string, reviewId: string, body: { outcome?: string; reason?: string } = {}) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/reviews/${reviewId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  submitFeedback: (runId: string, body: Record<string, unknown>) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  workspace: (runId: string) =>
    parse<Workspace>(apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/workspace`, { cache: "no-store" })),
  snapshot: (runId: string, snapshotId: string) =>
    parse<Record<string, unknown>>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/snapshots/${snapshotId}`, { cache: "no-store" }),
    ),
  exportUrl: (runId: string, format: string, snapshotId?: string) => {
    const query = new URLSearchParams({ format });
    if (snapshotId) query.set("snapshot_id", snapshotId);
    return `${apiUrl}/api/v1/research-runs/${runId}/export?${query}`;
  },
  listTemplates: () =>
    parse<
      Array<{
        id: string;
        name: string;
        goal: string;
        research_mode: "quick" | "standard" | "deep";
        output_language: string;
        created_at: string;
        updated_at: string;
      }>
    >(apiFetch(`${apiUrl}/api/v1/research-templates`, { cache: "no-store" })),
  createTemplate: (body: {
    name: string;
    goal: string;
    research_mode: "quick" | "standard" | "deep";
    output_language: string;
  }) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-templates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
    deleteTemplate: (templateId: string) =>
    apiFetch(`${apiUrl}/api/v1/research-templates/${templateId}`, { method: "DELETE" }).then((response) => {
      if (!response.ok && response.status !== 204) throw new Error(`Request failed (${response.status})`);
    }),
  followUp: (runId: string, body: { goal: string; inherit_source_preferences?: boolean }) =>
    parse<{ run_id: string }>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/follow-up`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  sourcePreferences: (runId: string) =>
    parse<Array<{ id: string; action: string; identity_kind: string; identity_value: string; reason: string }>>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/source-preferences`, { cache: "no-store" }),
    ),
  setSourcePreference: (runId: string, body: { action: "pin" | "exclude"; identity_kind: "url" | "domain"; identity_value: string; reason?: string }) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/source-preferences`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  deleteSourcePreference: (runId: string, preferenceId: string) =>
    apiFetch(`${apiUrl}/api/v1/research-runs/${runId}/source-preferences/${preferenceId}`, { method: "DELETE" }).then(
      (response) => {
        if (!response.ok && response.status !== 204) throw new Error(`Request failed (${response.status})`);
      },
    ),
  diffRuns: (leftId: string, rightId: string) =>
    parse<Record<string, unknown>>(
      apiFetch(`${apiUrl}/api/v1/research-runs/${leftId}/diff/${rightId}`, { cache: "no-store" }),
    ),
  listMonitors: () => parse<Record<string, unknown>[]>(apiFetch(`${apiUrl}/api/v1/research-monitors`, { cache: "no-store" })),
  createMonitor: (body: Record<string, unknown>) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-monitors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  patchMonitor: (id: string, body: Record<string, unknown>) =>
    parse(
      apiFetch(`${apiUrl}/api/v1/research-monitors/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  deleteMonitor: (id: string) =>
    apiFetch(`${apiUrl}/api/v1/research-monitors/${id}`, { method: "DELETE" }).then((response) => {
      if (!response.ok && response.status !== 204) throw new Error(`Request failed (${response.status})`);
    }),
  runMonitorNow: (id: string) =>
    parse<{ run_id: string }>(apiFetch(`${apiUrl}/api/v1/research-monitors/${id}/run-now`, { method: "POST" })),
  getMonitor: (id: string) =>
    parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/research-monitors/${id}`, { cache: "no-store" })),
  knowledgeRuns: () =>
    parse<Array<{ run_id: string; goal: string; page_count: number }>>(
      apiFetch(`${apiUrl}/api/v1/knowledge/runs`, { cache: "no-store" }),
    ),
  knowledgePages: (runId: string) =>
    parse<Array<Record<string, unknown>>>(
      apiFetch(`${apiUrl}/api/v1/knowledge/pages?run_id=${runId}`, { cache: "no-store" }),
    ),
  knowledgePage: (pageId: string) =>
    parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/knowledge/pages/${pageId}`, { cache: "no-store" })),
  knowledgeStatement: (statementId: string) =>
    parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/knowledge/statements/${statementId}`, { cache: "no-store" })),
  knowledgeSearch: (runId: string, q: string) =>
    parse<Record<string, unknown>>(
      apiFetch(`${apiUrl}/api/v1/knowledge/search?run_id=${runId}&q=${encodeURIComponent(q)}`, { cache: "no-store" }),
    ),
  knowledgeGraph: (runId: string) =>
    parse<Record<string, unknown>>(apiFetch(`${apiUrl}/api/v1/knowledge/graph?run_id=${runId}`, { cache: "no-store" })),
};
