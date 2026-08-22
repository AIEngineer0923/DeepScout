import type { Locale } from "@/i18n/messages";

const PAGE_TYPE: Record<string, Record<Locale, string>> = {
  topic: { en: "Topic page", it: "Pagina tematica" },
  entity: { en: "Entity page", it: "Pagina entità" },
  concept: { en: "Concept page", it: "Pagina concetto" },
  finding: { en: "Finding page", it: "Pagina risultato" },
  contradiction: { en: "Contradiction page", it: "Pagina contraddizione" },
  question: { en: "Question page", it: "Pagina domanda" },
};

const RELATION_TYPE: Record<string, Record<Locale, string>> = {
  supports: { en: "Supports", it: "Supporta" },
  refutes: { en: "Refutes", it: "Confuta" },
  contradicts: { en: "Contradicts", it: "Contraddice" },
  derived_from: { en: "Derived from", it: "Deriva da" },
  supersedes: { en: "Supersedes", it: "Sostituisce" },
  relates_to: { en: "Related to", it: "Correlato a" },
  mentions: { en: "Mentions", it: "Menziona" },
};

const STATEMENT_STATUS: Record<string, Record<Locale, string>> = {
  active: { en: "Active", it: "Attivo" },
  draft: { en: "Draft", it: "Bozza" },
  superseded: { en: "Superseded", it: "Sostituito" },
  contradicted: { en: "Contradicted", it: "Contraddetto" },
};

export function presentKnowledgePageType(pageType: string | null | undefined, locale: Locale): string {
  if (!pageType) return "—";
  return PAGE_TYPE[pageType]?.[locale] ?? pageType.replaceAll("_", " ");
}

export function presentKnowledgeRelation(relation: string | null | undefined, locale: Locale): string {
  if (!relation) return "—";
  const key = relation.toLowerCase();
  return RELATION_TYPE[key]?.[locale] ?? relation.replaceAll("_", " ");
}

export function presentKnowledgeStatus(status: string | null | undefined, locale: Locale): string {
  if (!status) return "—";
  return STATEMENT_STATUS[status]?.[locale] ?? status.replaceAll("_", " ");
}
