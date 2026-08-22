import type { Locale } from "@/i18n/messages";

const MONITOR_STATUS: Record<string, Record<Locale, string>> = {
  active: { en: "Active", it: "Attivo" },
  disabled: { en: "Paused", it: "In pausa" },
  running: { en: "Running", it: "In esecuzione" },
  failed: { en: "Failed", it: "Non riuscito" },
  waiting_for_review: { en: "Waiting for review", it: "In attesa di revisione" },
};

const SCHEDULE_KIND: Record<string, Record<Locale, string>> = {
  daily: { en: "Daily", it: "Giornaliero" },
  weekly: { en: "Weekly", it: "Settimanale" },
  interval: { en: "Interval", it: "A intervalli" },
};

export function presentMonitorStatus(status: string | null | undefined, locale: Locale): string {
  if (!status) return "—";
  return MONITOR_STATUS[status]?.[locale] ?? status.replaceAll("_", " ");
}

export function presentScheduleKind(kind: string | null | undefined, locale: Locale): string {
  if (!kind) return "—";
  return SCHEDULE_KIND[kind]?.[locale] ?? kind.replaceAll("_", " ");
}

export function formatMonitorTimestamp(value: string | null | undefined, locale: Locale): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale === "it" ? "it-IT" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
