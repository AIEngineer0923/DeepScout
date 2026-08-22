import type { Locale } from "@/i18n/messages";
import type { Workspace } from "@/lib/types";
import { displayWorkerName, displayWorkerTask } from "@/presentation/demo";
import { presentWorkerIndex } from "@/presentation/fields";

export function normalizePresentationText(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

export function truncatePresentationText(text: string, maxLen = 96): string {
  const cleaned = text.trim().replace(/\s+/g, " ");
  if (cleaned.length <= maxLen) return cleaned;
  const slice = cleaned.slice(0, maxLen);
  const lastSpace = slice.lastIndexOf(" ");
  const head = (lastSpace > 48 ? slice.slice(0, lastSpace) : slice).trim();
  return `${head}…`;
}

export function textsAreEquivalent(a: string, b: string): boolean {
  const left = normalizePresentationText(a);
  const right = normalizePresentationText(b);
  if (!left || !right) return false;
  if (left === right) return true;
  const shorter = left.length <= right.length ? left : right;
  const longer = left.length <= right.length ? right : left;
  return longer.startsWith(shorter) && shorter.length >= 40;
}

function cleanedWorkerName(workspace: Workspace, workerId: string, fallback: string): string {
  const name = displayWorkerName(workspace, workerId, fallback).trim();
  return name.replace(/^W\d+\s*(?:·|-)\s*/i, "").trim();
}

export function presentWorkerFullTask(
  workspace: Workspace,
  workerId: string,
  fallback: string,
): string {
  return displayWorkerTask(workspace, workerId, fallback).trim();
}

export function presentWorkerCardTitle(
  workspace: Workspace,
  workerId: string,
  locale: Locale,
): string {
  const worker = workspace.workers.find((item) => item.worker_id === workerId);
  if (!worker) return locale === "it" ? "Ricercatore" : "Researcher";

  const cleanedName = cleanedWorkerName(workspace, workerId, worker.display_name);
  if (cleanedName && !/^W\d+$/i.test(cleanedName)) {
    return truncatePresentationText(cleanedName, 96);
  }

  const task = presentWorkerFullTask(workspace, workerId, worker.assigned_task);
  if (task && !/^W\d+\b/i.test(task)) {
    return truncatePresentationText(task, 96);
  }

  return presentWorkerIndex(workspace, worker.index, locale);
}

export function presentWorkerSecondarySummary(
  workspace: Workspace,
  workerId: string,
): string | null {
  const worker = workspace.workers.find((item) => item.worker_id === workerId);
  if (!worker) return null;

  const title = presentWorkerCardTitle(workspace, workerId, "en");
  const fullTask = presentWorkerFullTask(workspace, workerId, worker.assigned_task);
  if (!fullTask || textsAreEquivalent(title, fullTask)) return null;
  if (fullTask.length <= title.length + 24) return null;
  return truncatePresentationText(fullTask, 140);
}
