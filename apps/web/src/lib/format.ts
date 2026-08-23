const ACTIVE = new Set(["running", "pending", "researching"]);

export function formatCost(value: number | null | undefined, status?: string, unknownLabel = "Unknown"): string {
  if (value == null || status === "unknown") return unknownLabel;
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

export function formatTokens(value: number | null | undefined, unknownLabel = "Unknown"): string {
  if (value == null) return unknownLabel;
  return value.toLocaleString();
}

export function formatStatus(status: string): string {
  return status.replaceAll("_", " ");
}

export function formatResearchMode(mode: string, t: (key: string) => string): string {
  const key = `researchMode.${mode}`;
  const translated = t(key);
  return translated === key ? mode.replaceAll("_", " ") : translated;
}

export function statusTone(status: string): "ok" | "run" | "warn" | "bad" | "muted" {
  const value = status.toLowerCase();
  if (["completed", "fetched", "supported", "verified", "connected", "ok"].includes(value)) return "ok";
  if (ACTIVE.has(value) || value === "in progress") return "run";
  if (["budget_exhausted", "partially_verified", "blocked"].includes(value)) return "warn";
  if (["failed", "cancelled", "refuted", "contradicted"].includes(value)) return "bad";
  return "muted";
}

export function relativeTime(iso: string | null | undefined, locale = "en"): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const delta = Date.now() - then;
  const minutes = Math.round(delta / 60000);
  if (Math.abs(minutes) < 1) return locale === "it" ? "adesso" : "just now";
  if (Math.abs(minutes) < 60) return locale === "it" ? `${minutes} min fa` : `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return locale === "it" ? `${hours} h fa` : `${hours}h ago`;
  return new Date(iso).toLocaleString(locale === "it" ? "it-IT" : "en-US");
}

/** Stopwatch reading for work still in flight. Rolls over to h:mm:ss past an hour. */
export function elapsed(from: string | null, to?: string | null): string {
  if (!from) return "—";
  const start = new Date(from).getTime();
  const end = to ? new Date(to).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "—";
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  const hh = Math.floor(seconds / 3600);
  const mm = Math.floor((seconds % 3600) / 60);
  const ss = seconds % 60;
  const tail = `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  return hh > 0 ? `${hh}:${tail}` : tail;
}

/**
 * How long a finished run took. A completed run has a fixed duration, so it is
 * read as a quantity ("12 min 30 s") rather than as a ticking stopwatch.
 */
export function formatDuration(from: string | null, to: string | null): string {
  if (!from || !to) return "—";
  const start = new Date(from).getTime();
  const end = new Date(to).getTime();
  if (Number.isNaN(start) || Number.isNaN(end)) return "—";
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  // h / min / s read the same in both supported locales.
  if (seconds < 60) return `${seconds} s`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`;
  const rest = seconds % 60;
  return rest > 0 ? `${minutes} min ${rest} s` : `${minutes} min`;
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
