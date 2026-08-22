const ARCHITECTURE_KEYS: Record<string, string> = {
  orchestrator: "arch.orchestrator",
  planner: "arch.planner",
  workers: "arch.workers",
  extraction: "arch.extraction",
  verification: "arch.verification",
  quality: "arch.quality",
  synthesis: "arch.synthesis",
  report: "arch.report",
};

const PARENT_LABEL_KEYS: Record<string, string> = {
  "Research Orchestrator": "arch.orchestrator",
  "Planner Agent": "arch.planner",
  "Research Workers": "arch.workers",
  "Extraction Engine": "arch.extraction",
  "Verification Engine": "arch.verification",
  "Quality Critic": "arch.quality",
  "Synthesis Agent": "arch.synthesis",
  "Report Engine": "arch.report",
};

export function presentArchitectureLabel(
  key: string,
  fallback: string,
  t: (messageKey: string) => string,
): string {
  const messageKey = ARCHITECTURE_KEYS[key];
  if (!messageKey) return fallback;
  const translated = t(messageKey);
  return translated === messageKey ? fallback : translated;
}

export function presentParentLabel(parent: string, t: (messageKey: string) => string): string {
  const messageKey = PARENT_LABEL_KEYS[parent];
  if (!messageKey) return parent;
  const translated = t(messageKey);
  return translated === messageKey ? parent : translated;
}
