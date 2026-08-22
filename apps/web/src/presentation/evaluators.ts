import type { Locale } from "@/i18n/messages";

export type EvaluatorPresentation = {
  title: Record<Locale, string>;
  description: Record<Locale, string>;
  passWhenTrue?: boolean;
  isRate?: boolean;
  isScore?: boolean;
};

const EVALUATORS: Record<string, EvaluatorPresentation> = {
  claim_has_evidence: {
    title: { en: "Claim coverage", it: "Copertura delle affermazioni" },
    description: {
      en: "Every verified claim is supported by at least one source.",
      it: "Ogni affermazione verificata dispone di almeno una fonte.",
    },
    passWhenTrue: true,
  },
  citation_correctness: {
    title: { en: "Citation validity", it: "Validità delle citazioni" },
    description: {
      en: "Citations point to the correct passages in the captured sources.",
      it: "Le citazioni rimandano correttamente ai passaggi nelle fonti acquisite.",
    },
    passWhenTrue: true,
  },
  provenance_complete: {
    title: { en: "Evidence consistency", it: "Coerenza delle evidenze" },
    description: {
      en: "Evidence, claims, and captured content belong to the same research run.",
      it: "Evidenze, affermazioni e contenuti acquisiti appartengono alla stessa ricerca.",
    },
    passWhenTrue: true,
  },
  unsupported_claim_rate: {
    title: { en: "Unsupported claims", it: "Affermazioni senza supporto" },
    description: {
      en: "Verified claims should not remain without supporting evidence.",
      it: "Le affermazioni verificate non dovrebbero restare prive di evidenze.",
    },
    isRate: true,
  },
  ragas_faithfulness: {
    title: { en: "Faithfulness to sources", it: "Fedeltà alle fonti" },
    description: {
      en: "The final answer stays faithful to the captured source material.",
      it: "La risposta finale resta fedele al materiale delle fonti acquisite.",
    },
    isScore: true,
  },
  hallucination: {
    title: { en: "Hallucination risk", it: "Rischio di allucinazioni" },
    description: {
      en: "Checks whether the answer invents facts beyond the available evidence.",
      it: "Verifica se la risposta inventa fatti oltre le evidenze disponibili.",
    },
    isScore: true,
  },
  correctness: {
    title: { en: "Correctness", it: "Correttezza" },
    description: {
      en: "Measures whether the answer is factually correct against references.",
      it: "Misura se la risposta è corretta rispetto ai riferimenti.",
    },
    isScore: true,
  },
  assertions: {
    title: { en: "Assertion checks", it: "Verifiche sulle affermazioni" },
    description: {
      en: "Deterministic checks on required claims and report structure.",
      it: "Verifiche deterministiche su affermazioni e struttura del report.",
    },
    passWhenTrue: true,
  },
  conciseness: {
    title: { en: "Conciseness", it: "Concisione" },
    description: {
      en: "Evaluates whether the answer is appropriately concise.",
      it: "Valuta se la risposta è sufficientemente concisa.",
    },
    isScore: true,
  },
  task_completion: {
    title: { en: "Research completion", it: "Completamento della ricerca" },
    description: {
      en: "The research run reached a terminal completed state.",
      it: "La ricerca ha raggiunto uno stato finale completato.",
    },
    passWhenTrue: true,
  },
  budget_compliance: {
    title: { en: "Budget compliance", it: "Rispetto del budget" },
    description: {
      en: "The run stayed within the configured research budget.",
      it: "La ricerca è rimasta entro il budget configurato.",
    },
    passWhenTrue: true,
  },
  duplicate_work: {
    title: { en: "Duplicate work", it: "Lavoro duplicato" },
    description: {
      en: "Detects unnecessary repeated research tasks.",
      it: "Rileva attività di ricerca ripetute inutilmente.",
    },
    passWhenTrue: true,
  },
  plan_adherence: {
    title: { en: "Plan adherence", it: "Aderenza al piano" },
    description: {
      en: "Execution followed the planned research steps.",
      it: "L'esecuzione ha seguito i passaggi pianificati.",
    },
    passWhenTrue: true,
  },
};

const CATEGORY_LABELS: Record<string, Record<Locale, string>> = {
  grounding: { en: "Evidence quality", it: "Qualità delle evidenze" },
  quality: { en: "Answer quality", it: "Qualità della risposta" },
  security: { en: "Security", it: "Sicurezza" },
  safety: { en: "Safety", it: "Sicurezza dei contenuti" },
  trajectory: { en: "Execution quality", it: "Qualità dell'esecuzione" },
  efficiency: { en: "Efficiency", it: "Efficienza" },
  retrieval: { en: "Retrieval quality", it: "Qualità del retrieval" },
  plan: { en: "Planning", it: "Pianificazione" },
  agent_safety: { en: "Agent safety", it: "Sicurezza dell'agente" },
  conversation: { en: "Conversation", it: "Conversazione" },
  image: { en: "Image", it: "Immagini" },
  voice: { en: "Voice", it: "Voce" },
  create: { en: "Custom evaluators", it: "Valutatori personalizzati" },
};

const METHOD_LABELS: Record<string, Record<Locale, string>> = {
  deterministic_code: { en: "Automated check", it: "Verifica automatica" },
  llm_as_judge: { en: "AI model evaluation", it: "Valutazione tramite modello AI" },
  hybrid: { en: "Hybrid evaluation", it: "Valutazione ibrida" },
  trajectory_match: { en: "Trajectory match", it: "Confronto traiettoria" },
  trajectory_llm_judge: { en: "Trajectory AI review", it: "Revisione AI della traiettoria" },
  human_feedback: { en: "Human feedback", it: "Feedback umano" },
  not_applicable: { en: "Not applicable", it: "Non applicabile" },
};

const APPLICABILITY_LABELS: Record<string, Record<Locale, string>> = {
  active_now: { en: "Available", it: "Disponibile" },
  offline_only: { en: "Advanced evaluation", it: "Valutazione avanzata" },
  online_ready: { en: "Available online", it: "Disponibile online" },
  future_modality_gated: { en: "Future capability", it: "Funzionalità futura" },
  not_applicable_by_design: { en: "Not applicable", it: "Non applicabile" },
  unsupported_by_current_api: { en: "Not supported", it: "Non supportato" },
};

export function presentEvaluatorCategory(category: string, locale: Locale): string {
  return CATEGORY_LABELS[category]?.[locale] ?? category.replaceAll("_", " ");
}

export function presentEvaluator(
  evaluatorId: string,
  locale: Locale,
  fallbackDescription?: string,
): { title: string; description: string } {
  const entry = EVALUATORS[evaluatorId];
  if (entry) {
    return { title: entry.title[locale], description: entry.description[locale] };
  }
  return {
    title: fallbackDescription ?? evaluatorId.replaceAll("_", " "),
    description: fallbackDescription ?? "",
  };
}

export function presentEvaluatorMethod(method: string, locale: Locale): string {
  return METHOD_LABELS[method]?.[locale] ?? method.replaceAll("_", " ");
}

export function presentEvaluatorApplicability(applicability: string, locale: Locale): string {
  return APPLICABILITY_LABELS[applicability]?.[locale] ?? applicability.replaceAll("_", " ");
}

export function presentEvaluatorResult(
  evaluatorId: string,
  value: unknown,
  locale: Locale,
): string {
  if (value == null || value === "—") {
    return locale === "it" ? "Non valutato" : "Not evaluated";
  }
  const entry = EVALUATORS[evaluatorId];
  if (typeof value === "boolean") {
    if (value) return locale === "it" ? "Superato" : "Passed";
    return locale === "it" ? "Non superato" : "Failed";
  }
  if (typeof value === "number") {
    if (entry?.isRate) {
      const pct = value <= 1 ? Math.round(value * 100) : value;
      return locale === "it" ? `${pct}%` : `${pct}%`;
    }
    if (entry?.passWhenTrue) {
      if (value === 1) return locale === "it" ? "Superato" : "Passed";
      if (value === 0) return locale === "it" ? "Non superato" : "Failed";
    }
    if (entry?.isScore || value <= 1) {
      const formatted = value.toLocaleString(locale === "it" ? "it-IT" : "en-US", {
        maximumFractionDigits: 2,
      });
      return locale === "it" ? `Punteggio: ${formatted}` : `Score: ${formatted}`;
    }
    return String(value);
  }
  const text = String(value).toLowerCase();
  if (text === "true") return locale === "it" ? "Superato" : "Passed";
  if (text === "false") return locale === "it" ? "Non superato" : "Failed";
  return String(value);
}

export function evaluatorMeta(evaluatorId: string) {
  return EVALUATORS[evaluatorId];
}

export const FORBIDDEN_UI_PATTERNS = [
  "run.completed",
  "phase.started",
  "phase.completed",
  "claim_has_evidence",
  "citation_correctness",
  "provenance_complete",
  "unsupported_claim_rate",
  "ragas_faithfulness",
  "cost_supply_chain",
  "cell_metrics_safety",
  "text/html; charset",
  "deterministic code",
  "llm as judge",
  "active now",
  "offline only",
  "research_worker v1",
  "schedule_kind",
] as const;
