import type { Locale } from "@/i18n/messages";

type Labels = Record<Locale, string>;

function lookup(
  labels: Record<string, Labels>,
  value: string | null | undefined,
  locale: Locale,
): string {
  if (!value) return "—";
  return labels[value.toLowerCase()]?.[locale] ?? (locale === "it" ? "Non disponibile" : "Unavailable");
}

const IDENTITY_ROLES: Record<string, Labels> = {
  operator: { en: "Operator", it: "Operatore" },
  authenticated: { en: "Authenticated", it: "Autenticato" },
  anonymous: { en: "Anonymous", it: "Anonimo" },
  visitor: { en: "Visitor", it: "Visitatore" },
};

const PHASES: Record<string, Labels> = {
  plan: { en: "Planning", it: "Pianificazione" },
  research: { en: "Research", it: "Ricerca" },
  compile_knowledge: { en: "Knowledge compilation", it: "Compilazione conoscenza" },
  fetch: { en: "Source capture", it: "Acquisizione fonti" },
  index: { en: "Indexing", it: "Indicizzazione" },
  extract: { en: "Evidence extraction", it: "Estrazione evidenze" },
  verify: { en: "Verification", it: "Verifica" },
  contradiction: { en: "Contradiction review", it: "Analisi contraddizioni" },
  critic: { en: "Quality review", it: "Controllo qualità" },
  synthesis: { en: "Synthesis", it: "Sintesi" },
  report: { en: "Report", it: "Report" },
  completed: { en: "Completed", it: "Completata" },
  pending: { en: "Pending", it: "In attesa" },
};

const JOBS: Record<string, Labels> = {
  execute_run: { en: "Research execution", it: "Esecuzione ricerca" },
  resume_run: { en: "Research resume", it: "Ripresa ricerca" },
  run_monitor: { en: "Monitor execution", it: "Esecuzione monitor" },
  pending: { en: "Pending", it: "In attesa" },
  queued: { en: "Queued", it: "In coda" },
  claimed: { en: "Claimed", it: "Assegnato" },
  running: { en: "Running", it: "In corso" },
  completed: { en: "Completed", it: "Completato" },
  failed: { en: "Failed", it: "Non riuscito" },
  cancelled: { en: "Cancelled", it: "Annullato" },
};

const COST_STATUSES: Record<string, Labels> = {
  known: { en: "Known", it: "Noto" },
  exact: { en: "Exact", it: "Esatto" },
  estimated: { en: "Estimated", it: "Stimato" },
  partial: { en: "Partial", it: "Parziale" },
  unknown: { en: "Unknown", it: "Sconosciuto" },
};

const REVIEW_REASONS: Record<string, Labels> = {
  budget_extension: { en: "Budget extension", it: "Estensione del budget" },
  high_risk_action: { en: "High-risk action", it: "Azione ad alto rischio" },
  insufficient_evidence: { en: "Insufficient evidence", it: "Evidenze insufficienti" },
};

const HEALTH_KEYS: Record<string, Labels> = {
  api: { en: "API", it: "API" },
  postgres: { en: "PostgreSQL", it: "PostgreSQL" },
  vector_store: { en: "Vector retrieval", it: "Retrieval vettoriale" },
  langsmith: { en: "LangSmith tracing", it: "Tracciamento LangSmith" },
};

const HEALTH_STATUSES: Record<string, Labels> = {
  ok: { en: "Available", it: "Disponibile" },
  connected: { en: "Connected", it: "Connesso" },
  off: { en: "Off", it: "Disattivato" },
  not_configured: { en: "Not configured", it: "Non configurato" },
  unavailable: { en: "Unavailable", it: "Non disponibile" },
  authentication_required: { en: "Sign-in required", it: "Accesso richiesto" },
  pgvector_ready: { en: "Ready", it: "Pronto" },
  embedding_not_configured: { en: "Embedding provider not configured", it: "Provider embedding non configurato" },
  embedding_provider_unsupported: { en: "Embedding provider unsupported", it: "Provider embedding non supportato" },
};

export const presentIdentityRole = (value: string | undefined, locale: Locale) =>
  lookup(IDENTITY_ROLES, value, locale);

export const presentRuntimePhase = (value: string | undefined, locale: Locale) =>
  lookup(PHASES, value, locale);

export const presentJob = (value: string | undefined | null, locale: Locale) =>
  lookup(JOBS, value, locale);

export const presentCostStatus = (value: string | undefined, locale: Locale) =>
  lookup(COST_STATUSES, value, locale);

export const presentReviewReason = (value: string | undefined, locale: Locale) =>
  lookup(REVIEW_REASONS, value, locale);

export const presentHealthKey = (value: string, locale: Locale) =>
  HEALTH_KEYS[value]?.[locale] ?? (locale === "it" ? "Servizio" : "Service");

export const presentHealthStatus = (value: string, locale: Locale) =>
  lookup(HEALTH_STATUSES, value, locale);

export function presentBoolean(value: unknown, locale: Locale): string {
  if (typeof value !== "boolean") return "—";
  return value ? (locale === "it" ? "Sì" : "Yes") : (locale === "it" ? "No" : "No");
}

export function presentCheckpointRole(value: string | undefined, locale: Locale): string {
  if (value === "worker_execution_snapshot") {
    return locale === "it" ? "Snapshot durable del worker" : "Durable worker snapshot";
  }
  if (value === "none" || !value) return locale === "it" ? "Nessuno" : "None";
  return locale === "it" ? "Checkpoint tecnico" : "Technical checkpoint";
}
