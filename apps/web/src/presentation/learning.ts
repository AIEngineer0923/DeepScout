import type { Locale } from "@/i18n/messages";

const FAILURE_CLASS: Record<string, Record<Locale, string>> = {
  planning_failure: { en: "Planning failure", it: "Errore di pianificazione" },
  retrieval_failure: { en: "Retrieval failure", it: "Errore di recupero" },
  evidence_failure: { en: "Evidence failure", it: "Errore di evidenza" },
  claim_failure: { en: "Claim failure", it: "Errore di affermazione" },
  coverage_failure: { en: "Coverage failure", it: "Errore di copertura" },
  synthesis_failure: { en: "Synthesis failure", it: "Errore di sintesi" },
  citation_failure: { en: "Citation failure", it: "Errore di citazione" },
  evaluation_failure: { en: "Evaluation failure", it: "Errore di valutazione" },
  cost_failure: { en: "Cost failure", it: "Errore di costo" },
  runtime_failure: { en: "Runtime failure", it: "Errore di runtime" },
  security_failure: { en: "Security failure", it: "Errore di sicurezza" },
  hitl_failure: { en: "Human review failure", it: "Errore di revisione umana" },
  opportunity: { en: "Improvement opportunity", it: "Opportunità di miglioramento" },
};

const CANDIDATE_TYPE: Record<string, Record<Locale, string>> = {
  configuration: { en: "Configuration", it: "Configurazione" },
  policy: { en: "Policy", it: "Policy" },
  prompt: { en: "Prompt", it: "Prompt" },
  routing: { en: "Routing", it: "Instradamento" },
  query_strategy: { en: "Query strategy", it: "Strategia di query" },
  retrieval_parameter: { en: "Retrieval parameter", it: "Parametro di recupero" },
  rerank_policy: { en: "Rerank policy", it: "Policy di rerank" },
  planner_policy: { en: "Planner policy", it: "Policy del planner" },
  worker_policy: { en: "Worker policy", it: "Policy degli agenti" },
  coverage_policy: { en: "Coverage policy", it: "Policy di copertura" },
  synthesis_policy: { en: "Synthesis policy", it: "Policy di sintesi" },
  stopping_policy: { en: "Stopping policy", it: "Policy di arresto" },
  code_proposal: { en: "Code proposal", it: "Proposta di codice" },
};

const CANDIDATE_STATUS: Record<string, Record<Locale, string>> = {
  draft: { en: "Draft", it: "Bozza" },
  evaluated: { en: "Evaluated", it: "Valutato" },
  requires_human_review: { en: "Needs review", it: "Richiede revisione" },
  approved: { en: "Approved", it: "Approvato" },
  rejected: { en: "Rejected", it: "Rifiutato" },
  promoted: { en: "Promoted", it: "Promosso" },
  rolled_back: { en: "Rolled back", it: "Ripristinato" },
};

const RISK_LEVEL: Record<string, Record<Locale, string>> = {
  low_risk_auto_eligible: { en: "Low risk", it: "Rischio basso" },
  medium_risk_hitl: { en: "Medium risk", it: "Rischio medio" },
  high_risk_human_only: { en: "High risk", it: "Rischio alto" },
};

const REVIEW_STATE: Record<string, Record<Locale, string>> = {
  observed: { en: "Observed", it: "Osservato" },
  diagnosed: { en: "Diagnosed", it: "Diagnosticato" },
  candidate_pending: { en: "Candidate pending", it: "Candidato in attesa" },
  reviewed: { en: "Reviewed", it: "Revisionato" },
  promoted: { en: "Promoted", it: "Promosso" },
  rejected: { en: "Rejected", it: "Rifiutato" },
  archived: { en: "Archived", it: "Archiviato" },
};

const SUBSYSTEM: Record<string, Record<Locale, string>> = {
  planning: { en: "Planning", it: "Pianificazione" },
  retrieval: { en: "Retrieval", it: "Recupero" },
  evidence: { en: "Evidence", it: "Evidenza" },
  claims: { en: "Claims", it: "Affermazioni" },
  coverage: { en: "Coverage", it: "Copertura" },
  synthesis: { en: "Synthesis", it: "Sintesi" },
  citation: { en: "Citation", it: "Citazione" },
  evaluation: { en: "Evaluation", it: "Valutazione" },
  cost: { en: "Cost", it: "Costo" },
  runtime: { en: "Runtime", it: "Runtime" },
  security: { en: "Security", it: "Sicurezza" },
  hitl: { en: "Human review", it: "Revisione umana" },
};

const PROMOTION_VERDICT: Record<string, Record<Locale, string>> = {
  safe_to_promote: { en: "Safe to promote", it: "Sicuro da promuovere" },
  requires_human_review: { en: "Needs review", it: "Richiede revisione" },
  rejected: { en: "Rejected", it: "Rifiutato" },
  no_change: { en: "No change", it: "Nessun cambiamento" },
};

const AUDIT_EVENT: Record<string, Record<Locale, string>> = {
  policy_promoted: { en: "Policy promoted", it: "Policy promossa" },
  policy_rolled_back: { en: "Policy rolled back", it: "Policy ripristinata" },
};

const CANDIDATE_TYPE_RISK: Record<string, string> = {
  coverage_policy: "low_risk_auto_eligible",
  retrieval_parameter: "low_risk_auto_eligible",
  query_strategy: "low_risk_auto_eligible",
  stopping_policy: "low_risk_auto_eligible",
  configuration: "low_risk_auto_eligible",
  rerank_policy: "low_risk_auto_eligible",
  routing: "low_risk_auto_eligible",
  policy: "medium_risk_hitl",
  planner_policy: "medium_risk_hitl",
  worker_policy: "medium_risk_hitl",
  synthesis_policy: "medium_risk_hitl",
  prompt: "high_risk_human_only",
  code_proposal: "high_risk_human_only",
};

function lookup(map: Record<string, Record<Locale, string>>, key: string | null | undefined, locale: Locale): string {
  if (!key) return "—";
  return map[key]?.[locale] ?? key.replaceAll("_", " ");
}

export function presentFailureClass(value: string | null | undefined, locale: Locale): string {
  return lookup(FAILURE_CLASS, value, locale);
}

export function presentCandidateType(value: string | null | undefined, locale: Locale): string {
  return lookup(CANDIDATE_TYPE, value, locale);
}

export function presentCandidateStatus(value: string | null | undefined, locale: Locale): string {
  return lookup(CANDIDATE_STATUS, value, locale);
}

export function presentRiskLevel(value: string | null | undefined, locale: Locale): string {
  return lookup(RISK_LEVEL, value, locale);
}

export function presentReviewState(value: string | null | undefined, locale: Locale): string {
  return lookup(REVIEW_STATE, value, locale);
}

export function presentLearningSubsystem(value: string | null | undefined, locale: Locale): string {
  return lookup(SUBSYSTEM, value, locale);
}

export function presentPromotionVerdict(value: string | null | undefined, locale: Locale): string {
  return lookup(PROMOTION_VERDICT, value, locale);
}

export function presentAuditEventType(value: string | null | undefined, locale: Locale): string {
  return lookup(AUDIT_EVENT, value, locale);
}

export function riskForCandidateType(candidateType: string | null | undefined): string {
  if (!candidateType) return "medium_risk_hitl";
  return CANDIDATE_TYPE_RISK[candidateType] ?? "medium_risk_hitl";
}

export function formatLearningTimestamp(value: string | null | undefined, locale: Locale): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale === "it" ? "it-IT" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
