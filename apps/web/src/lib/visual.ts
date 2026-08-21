/** Deterministic visual helpers for layout fidelity (no fake runtime data). */

export function workerProgress(state: string, index: number): number {
  if (state === "completed") return 100;
  if (state === "failed") return 100;
  if (["running", "claimed"].includes(state)) return [72, 48, 86][index % 3] ?? 60;
  if (state === "ready") return 24;
  return 0;
}

export function workerTone(index: number): "blue" | "green" | "purple" {
  return (["blue", "green", "purple"] as const)[index % 3];
}

export function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
  return (parts[0]?.slice(0, 2) ?? "DS").toUpperCase();
}
