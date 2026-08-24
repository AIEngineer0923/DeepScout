import type { Locale } from "@/i18n/messages";
import type { Workspace } from "@/lib/types";
import {
  displayTaskObjective,
  displayWorkerTask,
} from "@/presentation/demo";
import { presentWorkerCardTitle } from "@/presentation/workers";

export function presentOutputLanguage(code: string | null | undefined, locale: Locale): string {
  if (!code) return "—";
  const normalized = code.toLowerCase();
  if (normalized === "it" || normalized.startsWith("it")) {
    return locale === "it" ? "Italiano" : "Italian";
  }
  if (normalized === "en" || normalized.startsWith("en")) {
    return locale === "it" ? "Inglese" : "English";
  }
  return code;
}

export function presentSourceType(sourceType: string | null | undefined, locale: Locale): string {
  if (!sourceType) return "—";
  const labels: Record<string, Record<Locale, string>> = {
    web: { en: "Web page", it: "Pagina web" },
    web_page: { en: "Web page", it: "Pagina web" },
    official_source: { en: "Official source", it: "Fonte ufficiale" },
    academic_paper: { en: "Academic paper", it: "Paper accademico" },
    news_article: { en: "News article", it: "Articolo di notizie" },
    video: { en: "Video", it: "Video" },
    community_discussion: { en: "Community discussion", it: "Discussione della community" },
    repository: { en: "Repository", it: "Repository" },
    technical_documentation: { en: "Technical documentation", it: "Documentazione tecnica" },
    dataset: { en: "Dataset", it: "Dataset" },
    feed: { en: "RSS / Atom feed", it: "Feed RSS / Atom" },
    structured_api: { en: "Structured public data", it: "Dati pubblici strutturati" },
    pdf: { en: "PDF document", it: "Documento PDF" },
    article: { en: "Article", it: "Articolo" },
    document: { en: "Document", it: "Documento" },
  };
  return labels[sourceType]?.[locale] ?? sourceType;
}

export function presentSourceAuthority(
  authority: string | null | undefined,
  locale: Locale,
): string {
  if (!authority) return "—";
  const labels: Record<string, Record<Locale, string>> = {
    primary: { en: "Primary source", it: "Fonte primaria" },
    secondary: { en: "Secondary source", it: "Fonte secondaria" },
    tertiary: { en: "Tertiary source", it: "Fonte terziaria" },
    community: { en: "Community source", it: "Fonte della community" },
    unknown: { en: "Authority not established", it: "Autorevolezza non determinata" },
  };
  return labels[authority]?.[locale] ?? authority.replaceAll("_", " ");
}

export function presentEvidenceRole(
  role: string | null | undefined,
  locale: Locale,
): string {
  if (!role) return "—";
  const labels: Record<string, Record<Locale, string>> = {
    official_factual_record: { en: "Official factual record", it: "Riscontro ufficiale" },
    scholarly_evidence: { en: "Scholarly evidence", it: "Evidenza scientifica" },
    current_reporting: { en: "Current reporting", it: "Cronaca attuale" },
    audiovisual_primary_or_commentary: {
      en: "Audiovisual evidence or commentary",
      it: "Evidenza audiovisiva o commento",
    },
    user_experience_or_sentiment: {
      en: "User experience or sentiment",
      it: "Esperienza o opinione degli utenti",
    },
    software_implementation: { en: "Software implementation", it: "Implementazione software" },
    technical_specification: { en: "Technical specification", it: "Specifica tecnica" },
    quantitative_data: { en: "Quantitative data", it: "Dati quantitativi" },
    documentary_evidence: { en: "Documentary evidence", it: "Evidenza documentale" },
    freshness_discovery: { en: "Freshness and discovery", it: "Attualità e scoperta" },
    structured_factual_record: { en: "Structured factual record", it: "Riscontro strutturato" },
    general_evidence: { en: "General evidence", it: "Evidenza generale" },
  };
  return labels[role]?.[locale] ?? role.replaceAll("_", " ");
}

export function presentPreference(
  preference: string | null | undefined,
  locale: Locale,
): string {
  if (!preference || preference === "normal") {
    return locale === "it" ? "Normale" : "Normal";
  }
  const labels: Record<string, Record<Locale, string>> = {
    pinned: { en: "Pinned", it: "Fissata" },
    excluded: { en: "Excluded", it: "Esclusa" },
  };
  return labels[preference]?.[locale] ?? preference.replaceAll("_", " ");
}

export function presentMimeType(mime: string | null | undefined, locale: Locale): string {
  if (!mime) return "—";
  const lower = mime.toLowerCase();
  if (lower.includes("text/html")) return locale === "it" ? "Pagina web" : "Web page";
  if (lower.includes("application/pdf")) return locale === "it" ? "Documento PDF" : "PDF document";
  if (lower.startsWith("text/")) return locale === "it" ? "Testo acquisito" : "Captured text";
  return locale === "it" ? "Contenuto acquisito" : "Captured content";
}

export function presentSnapshotSummary(
  item: { word_count?: number | null; evidence_count?: number | null },
  locale: Locale,
): string {
  const parts: string[] = [];
  if (item.word_count != null && item.word_count > 0) {
    parts.push(
      locale === "it"
        ? `${item.word_count.toLocaleString("it-IT")} parole`
        : `${item.word_count.toLocaleString("en-US")} words`,
    );
  }
  if (item.evidence_count != null && item.evidence_count > 0) {
    parts.push(
      locale === "it"
        ? `${item.evidence_count} evidenze collegate`
        : `${item.evidence_count} linked evidence`,
    );
  }
  return parts.length ? parts.join(" · ") : locale === "it" ? "Snapshot disponibile" : "Snapshot available";
}

export function presentWorkerIndex(
  workspace: Workspace,
  workerIndex: number | null | undefined,
  locale: Locale,
): string {
  if (!workerIndex) return "—";
  return locale === "it" ? `Ricercatore ${workerIndex}` : `Researcher ${workerIndex}`;
}

export function presentWorkerHeadline(
  workspace: Workspace,
  workerId: string,
  locale: Locale,
): string {
  return presentWorkerCardTitle(workspace, workerId, locale);
}

export function presentTaskKey(
  workspace: Workspace,
  taskKey: string | null | undefined,
  fallbackObjective?: string | null,
): string {
  if (!taskKey) return "—";
  const task = workspace.tasks.find((item) => item.task_key === taskKey || item.id === taskKey);
  const objective = task?.objective ?? fallbackObjective ?? taskKey;
  return displayTaskObjective(workspace, taskKey, objective);
}

export function presentResearchCost(
  value: number | null | undefined,
  locale: Locale,
): string {
  if (value == null) return "—";
  const formatted = value.toLocaleString(locale === "it" ? "it-IT" : "en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value < 0.01 ? 4 : 2,
    maximumFractionDigits: value < 0.01 ? 4 : 2,
  });
  return formatted;
}

export function presentWorkerLabel(
  workspace: Workspace,
  workerId: string | null | undefined,
  locale: Locale,
): string {
  if (!workerId) return "—";
  return presentWorkerHeadline(workspace, workerId, locale);
}
