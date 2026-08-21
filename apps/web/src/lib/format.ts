const ACTIVE = new Set(["running", "pending", "researching"]);

export function formatCost(value: number | null | undefined, status?: string): string {
  if (value == null || status === "unknown") return "Unknown";
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

export function formatTokens(value: number | null | undefined): string {
  if (value == null) return "Unknown";
  return value.toLocaleString();
}

export function formatStatus(status: string): string {
  return status.replaceAll("_", " ");
}

export function statusTone(status: string): "ok" | "run" | "warn" | "bad" | "muted" {
  const value = status.toLowerCase();
  if (["completed", "fetched", "supported", "verified", "connected", "ok"].includes(value)) return "ok";
  if (ACTIVE.has(value) || value === "in progress") return "run";
  if (["budget_exhausted", "partially_verified", "blocked"].includes(value)) return "warn";
  if (["failed", "cancelled", "refuted", "contradicted"].includes(value)) return "bad";
  return "muted";
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const delta = Date.now() - then;
  const minutes = Math.round(delta / 60000);
  if (Math.abs(minutes) < 1) return "just now";
  if (Math.abs(minutes) < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return `${hours}h ago`;
  return new Date(iso).toLocaleString();
}

export function elapsed(from: string | null, to?: string | null): string {
  if (!from) return "—";
  const start = new Date(from).getTime();
  const end = to ? new Date(to).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  const mm = Math.floor(seconds / 60);
  const ss = seconds % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

export function phaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    plan: "Planning",
    research: "Research",
    fetch: "Research",
    extract: "Research",
    verify: "Verification",
    contradiction: "Verification",
    critic: "Verification",
    synthesis: "Synthesis",
    report: "Report",
  };
  return labels[phase] ?? phase;
}
