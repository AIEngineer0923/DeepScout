const LAST_RUN_KEY = "deepscout.last_run_id";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseRunId(pathname: string): string | null {
  const match = pathname.match(/\/(?:research|resume)\/([0-9a-f-]{36})/i);
  return match?.[1] ?? null;
}

export function readLastRunId(): string | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(LAST_RUN_KEY);
  return value && UUID.test(value) ? value : null;
}

export function rememberRunId(runId: string | null) {
  if (typeof window === "undefined" || !runId || !UUID.test(runId)) return;
  window.localStorage.setItem(LAST_RUN_KEY, runId);
}

export function clearLastRunId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LAST_RUN_KEY);
}
