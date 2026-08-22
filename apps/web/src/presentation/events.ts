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
  planning: { en: "Planning", it: "Pianificazione" },
  research: { en: "Research", it: "Ricerca" },
  verification: { en: "Verification", it: "Verifica" },
  synthesis: { en: "Conclusions", it: "Sintesi" },
  reporting: { en: "Reporting", it: "Report" },
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

export function presentEvent(
  type: string,
  locale: Locale,
  payload: Record<string, unknown> = {},
  workspace?: Workspace | null,
): { label: string; detail?: string; category: EventCategory; icon: string } {
  const entry = REGISTRY[type];
  const phase = typeof payload.phase === "string" ? payload.phase.toLowerCase() : "";
  const phaseLabel = phase ? PHASE_LABELS[phase]?.[locale] : undefined;

  if (entry) {
    let label = entry.label[locale];
    if (type === "phase.started" && phaseLabel) {
      label = locale === "it" ? `${phaseLabel} avviata` : `${phaseLabel} started`;
    }
    if (type === "phase.completed" && phaseLabel) {
      label = locale === "it" ? `${phaseLabel} completata` : `${phaseLabel} completed`;
    }
    const detail =
      typeof payload.task_key === "string" && workspace
        ? presentTaskKey(workspace, payload.task_key)
        : typeof payload.worker_id === "string" && workspace
          ? presentWorkerLabel(workspace, payload.worker_id, locale)
          : undefined;
    return {
      label,
      detail,
      category: entry.category,
      icon: entry.icon,
    };
  }

  return {
    label: humanizeRawEvent(type, locale),
    category: "system",
    icon: "●",
  };
}

export function eventMatchesFilter(type: string, filter: string): boolean {
  if (filter === "all") return true;
  const entry = REGISTRY[type];
  if (!entry) return filter === "system";
  if (filter === "phase") return entry.category === "phase";
  if (filter === "worker") return entry.category === "worker";
  if (filter === "source") return entry.category === "source";
  if (filter === "evidence") return entry.category === "evidence";
  if (filter === "quality") return entry.category === "quality";
  if (filter === "report") return entry.category === "report";
  return entry.category === filter;
}

export function isLowValueTimelineEvent(type: string): boolean {
  return type === "worker.progress" || type === "budget.updated" || type === "context.compacted";
}
