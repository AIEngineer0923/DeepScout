import type { Locale } from "@/i18n/messages";
import type { Workspace } from "@/lib/types";
import {
  displayTaskObjective,
  displayWorkerName,
} from "@/presentation/demo";

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
  const key = `sourceType.${sourceType}`;
  const labels: Record<string, Record<Locale, string>> = {
    web: { en: "Web page", it: "Pagina web" },
    pdf: { en: "PDF document", it: "Documento PDF" },
    article: { en: "Article", it: "Articolo" },
    document: { en: "Document", it: "Documento" },
  };
  return labels[sourceType]?.[locale] ?? sourceType;
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
  const worker = workspace.workers.find((item) => item.index === workerIndex);
  if (worker) {
    return displayWorkerName(workspace, worker.worker_id, worker.display_name);
  }
  return locale === "it" ? `Ricercatore ${workerIndex}` : `Researcher ${workerIndex}`;
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
  const worker = workspace.workers.find((item) => item.worker_id === workerId);
  if (worker) {
    return displayWorkerName(workspace, worker.worker_id, worker.display_name);
  }
  return locale === "it" ? "Ricercatore" : "Researcher";
}
