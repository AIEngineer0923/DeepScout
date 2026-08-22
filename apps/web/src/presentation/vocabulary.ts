import type { Locale } from "@/i18n/messages";

export type VocabularyConcept =
  | "research_run"
  | "worker"
  | "task"
  | "snapshot"
  | "evidence"
  | "claim"
  | "contradiction"
  | "evaluation"
  | "provider"
  | "model"
  | "retrieval"
  | "knowledge"
  | "report"
  | "phase"
  | "source"
  | "quality"
  | "critic"
  | "synthesis";

const VOCABULARY: Record<VocabularyConcept, Record<Locale, { label: string; help?: string; technical?: string }>> = {
  research_run: {
    en: { label: "Research", technical: "Run" },
    it: { label: "Ricerca", technical: "Run" },
  },
  worker: {
    en: { label: "Research agent", technical: "Worker" },
    it: { label: "Agente di ricerca", technical: "Worker" },
  },
  task: {
    en: { label: "Research task", technical: "Task" },
    it: { label: "Attività di ricerca", technical: "Task" },
  },
  snapshot: {
    en: {
      label: "Captured source",
      help: "A stored copy of content used during research.",
      technical: "Snapshot",
    },
    it: {
      label: "Copia acquisita",
      help: "Copia archiviata del contenuto utilizzato durante la ricerca.",
      technical: "Snapshot",
    },
  },
  evidence: {
    en: { label: "Evidence", technical: "Evidence" },
    it: { label: "Evidenza", technical: "Evidence" },
  },
  claim: {
    en: { label: "Finding", technical: "Claim" },
    it: { label: "Risultato", technical: "Claim" },
  },
  contradiction: {
    en: { label: "Potential contradiction", technical: "Contradiction" },
    it: { label: "Possibile contraddizione", technical: "Contraddizione" },
  },
  evaluation: {
    en: { label: "Quality check", technical: "Evaluation" },
    it: { label: "Controllo qualità", technical: "Valutazione" },
  },
  provider: {
    en: { label: "Provider", technical: "Provider" },
    it: { label: "Provider", technical: "Provider" },
  },
  model: {
    en: { label: "Model", technical: "Model" },
    it: { label: "Modello", technical: "Model" },
  },
  retrieval: {
    en: { label: "Evidence retrieval", technical: "Retrieval" },
    it: { label: "Ricerca nelle evidenze", technical: "Retrieval" },
  },
  knowledge: {
    en: { label: "Knowledge", technical: "Knowledge" },
    it: { label: "Conoscenza", technical: "Knowledge" },
  },
  report: {
    en: { label: "Final report", technical: "Report" },
    it: { label: "Report finale", technical: "Report" },
  },
  phase: {
    en: { label: "Phase", technical: "Phase" },
    it: { label: "Fase", technical: "Fase" },
  },
  source: {
    en: { label: "Source", technical: "Source" },
    it: { label: "Fonte", technical: "Fonte" },
  },
  quality: {
    en: { label: "Quality checks", technical: "Quality" },
    it: { label: "Controlli di qualità", technical: "Qualità" },
  },
  critic: {
    en: { label: "Quality review", technical: "Critic" },
    it: { label: "Controllo qualità", technical: "Critic" },
  },
  synthesis: {
    en: { label: "Conclusions", technical: "Synthesis" },
    it: { label: "Sintesi", technical: "Synthesis" },
  },
};

export function vocab(concept: VocabularyConcept, locale: Locale, mode: "normal" | "technical" = "normal") {
  const entry = VOCABULARY[concept][locale];
  if (mode === "technical" && entry.technical) return entry.technical;
  return entry.label;
}

export function vocabHelp(concept: VocabularyConcept, locale: Locale) {
  return VOCABULARY[concept][locale].help;
}
