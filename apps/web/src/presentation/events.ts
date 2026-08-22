import type { Locale } from "@/i18n/messages";
import type { Workspace } from "@/lib/types";
import { presentTaskKey, presentWorkerLabel } from "@/presentation/fields";

export type EventCategory = "run" | "phase" | "worker" | "source" | "evidence" | "quality" | "report" | "system";

type EventPresentation = {
  label: Record<Locale, string>;
  description?: Record<Locale, string>;
  category: EventCategory;
  icon: string;
};

const PHASE_LABELS: Record<string, Record<Locale, string>> = {
  plan: { en: "Planning", it: "Pianificazione" },
  research: { en: "Research", it: "Ricerca" },
  compile_knowledge: { en: "Compiled knowledge", it: "Conoscenza compilata" },
  fetch: { en: "Fetch", it: "Acquisizione" },
  index: { en: "Indexing", it: "Indicizzazione" },
  extract: { en: "Extraction", it: "Estrazione" },
  verify: { en: "Verification", it: "Verifica" },
  contradiction: { en: "Contradictions", it: "Contraddizioni" },
  critic: { en: "Quality review", it: "Controllo qualità" },
  synthesis: { en: "Synthesis", it: "Sintesi" },
  report: { en: "Report", it: "Report" },
};

/** Maps runtime phase names to timeline filter categories for phase.* events. */
const PHASE_FILTER_CATEGORY: Record<string, EventCategory> = {
  plan: "phase",
  research: "phase",
  compile_knowledge: "phase",
  fetch: "source",
  index: "phase",
  extract: "evidence",
  verify: "quality",
  contradiction: "quality",
  critic: "quality",
  synthesis: "report",
  report: "report",
};

const REGISTRY: Record<string, EventPresentation> = {
  "run.started": {
    label: { en: "Research started", it: "Ricerca avviata" },
    category: "run",
    icon: "●",
  },
  "run.completed": {
    label: { en: "Research completed", it: "Ricerca completata" },
    category: "run",
    icon: "✓",
  },
  "run.failed": {
    label: { en: "Research failed", it: "Ricerca non riuscita" },
    category: "run",
    icon: "✕",
  },
  "run.cancelled": {
    label: { en: "Research cancelled", it: "Ricerca annullata" },
    category: "run",
    icon: "✕",
  },
  "run.paused": {
    label: { en: "Research paused", it: "Ricerca in pausa" },
    category: "run",
    icon: "‖",
  },
  "phase.started": {
    label: { en: "Phase started", it: "Fase avviata" },
    category: "phase",
    icon: "●",
  },
  "phase.completed": {
    label: { en: "Phase completed", it: "Fase completata" },
    category: "phase",
    icon: "✓",
  },
  "task.ready": {
    label: { en: "Task ready", it: "Attività pronta" },
    category: "phase",
    icon: "●",
  },
  "worker.started": {
    label: { en: "Research agent started", it: "Ricercatore avviato" },
    category: "worker",
    icon: "●",
  },
  "worker.progress": {
    label: { en: "Research agent in progress", it: "Ricercatore in corso" },
    category: "worker",
    icon: "●",
  },
  "worker.completed": {
    label: { en: "Research agent completed", it: "Ricerca dell'agente completata" },
    category: "worker",
    icon: "✓",
  },
  "worker.failed": {
    label: { en: "Research agent failed", it: "Ricercatore non riuscito" },
    category: "worker",
    icon: "✕",
  },
  "workers.allocated": {
    label: { en: "Research agents assigned", it: "Agenti di ricerca assegnati" },
    category: "worker",
    icon: "●",
  },
  "source.discovered": {
    label: { en: "New source discovered", it: "Nuova fonte trovata" },
    category: "source",
    icon: "●",
  },
  "source.fetched": {
    label: { en: "Source captured", it: "Fonte acquisita" },
    category: "source",
    icon: "✓",
  },
  "claim.created": {
    label: { en: "Finding recorded", it: "Risultato registrato" },
    category: "evidence",
    icon: "●",
  },
  "evidence.created": {
    label: { en: "Evidence added", it: "Evidenza aggiunta" },
    category: "evidence",
    icon: "✓",
  },
  "contradiction.detected": {
    label: { en: "Potential contradiction detected", it: "Possibile contraddizione rilevata" },
    category: "quality",
    icon: "!",
  },
  "critic.started": {
    label: { en: "Quality review started", it: "Controllo qualità avviato" },
    category: "quality",
    icon: "●",
  },
  "critic.completed": {
    label: { en: "Quality review completed", it: "Controllo qualità completato" },
    category: "quality",
    icon: "✓",
  },
  "report.ready": {
    label: { en: "Final report ready", it: "Report finale pronto" },
    category: "report",
    icon: "✓",
  },
  "budget.updated": {
    label: { en: "Budget updated", it: "Budget aggiornato" },
    category: "system",
    icon: "●",
  },
  "review.requested": {
    label: { en: "Review requested", it: "Revisione richiesta" },
    category: "system",
    icon: "●",
  },
  "review.resolved": {
    label: { en: "Review resolved", it: "Revisione risolta" },
    category: "system",
    icon: "✓",
  },
  "skill.selected": {
    label: { en: "Skill selected", it: "Competenza selezionata" },
    category: "worker",
    icon: "●",
  },
  "replan.applied": {
    label: { en: "Plan updated", it: "Piano aggiornato" },
    category: "phase",
    icon: "●",
  },
  "context.compacted": {
    label: { en: "Context optimized", it: "Contesto ottimizzato" },
    category: "system",
    icon: "●",
  },
  "run.forked": {
    label: { en: "Research forked", it: "Ricerca derivata" },
    category: "run",
    icon: "●",
  },
};

function humanizeRawEvent(type: string, locale: Locale): string {
  const cleaned = type.replace(/[._]/g, " ");
  if (locale === "it") return `Evento: ${cleaned}`;
  return `Event: ${cleaned}`;
}

function hostnameFromUrl(value: string): string | undefined {
  try {
    return new URL(value).hostname;
  } catch {
    return value.length > 64 ? `${value.slice(0, 61)}…` : value;
  }
}

function eventCategory(type: string, payload: Record<string, unknown>): EventCategory {
  const entry = REGISTRY[type];
  if ((type === "phase.started" || type === "phase.completed") && typeof payload.phase === "string") {
    return PHASE_FILTER_CATEGORY[payload.phase.toLowerCase()] ?? "phase";
  }
  return entry?.category ?? "system";
}

function buildDetail(
  type: string,
  payload: Record<string, unknown>,
  workspace: Workspace | null | undefined,
  locale: Locale,
): string | undefined {
  const parts: string[] = [];

  if (typeof payload.task_key === "string" && workspace) {
    parts.push(presentTaskKey(workspace, payload.task_key));
  }
  if (typeof payload.worker_id === "string" && workspace) {
    parts.push(presentWorkerLabel(workspace, payload.worker_id, locale));
  }
  if (typeof payload.url === "string" && (type === "source.discovered" || type === "source.fetched")) {
    parts.push(hostnameFromUrl(payload.url) ?? payload.url);
  }
  if (typeof payload.skill === "string" && type === "skill.selected") {
    parts.push(payload.skill);
  }
  if (typeof payload.count === "number" && type === "workers.allocated") {
    parts.push(locale === "it" ? `${payload.count} agenti` : `${payload.count} agents`);
  }

  return parts.length ? parts.join(" · ") : undefined;
}

export function presentEvent(
  type: string,
  locale: Locale,
  payload: Record<string, unknown> = {},
  workspace?: Workspace | null,
): { label: string; detail?: string; category: EventCategory; icon: string } {
  const entry = REGISTRY[type];
  const phase = typeof payload.phase === "string" ? payload.phase.toLowerCase() : "";
  const phaseLabel = phase ? PHASE_LABELS[phase]?.[locale] : undefined;
  const category = eventCategory(type, payload);

  if (entry) {
    let label = entry.label[locale];
    if (type === "phase.started" && phaseLabel) {
      label = locale === "it" ? `${phaseLabel} avviata` : `${phaseLabel} started`;
    }
    if (type === "phase.completed" && phaseLabel) {
      label = locale === "it" ? `${phaseLabel} completata` : `${phaseLabel} completed`;
    }
    return {
      label,
      detail: buildDetail(type, payload, workspace, locale),
      category,
      icon: entry.icon,
    };
  }

  return {
    label: humanizeRawEvent(type, locale),
    category: "system",
    icon: "●",
  };
}

export function eventMatchesFilter(
  type: string,
  filter: string,
  payload: Record<string, unknown> = {},
): boolean {
  if (filter === "all") return true;
  const category = eventCategory(type, payload);
  if (filter === "phase") return category === "phase";
  if (filter === "worker") return category === "worker";
  if (filter === "source") return category === "source";
  if (filter === "evidence") return category === "evidence";
  if (filter === "quality") return category === "quality";
  if (filter === "report") return category === "report";
  return category === filter;
}

export function isLowValueTimelineEvent(type: string): boolean {
  return type === "worker.progress" || type === "budget.updated" || type === "context.compacted";
}

export function timelineDedupKey(type: string, payload: Record<string, unknown> = {}): string {
  if (type === "phase.started" || type === "phase.completed") {
    return `${type}:${String(payload.phase ?? "")}`;
  }
  if (type === "source.discovered" || type === "source.fetched") {
    return `${type}:${String(payload.url ?? payload.task_key ?? "")}`;
  }
  if (type === "worker.started" || type === "worker.completed" || type === "worker.failed") {
    return `${type}:${String(payload.worker_id ?? "")}:${String(payload.task_key ?? "")}`;
  }
  return `${type}:${JSON.stringify(payload)}`;
}
