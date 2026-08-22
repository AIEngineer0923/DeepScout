import type { Locale } from "@/i18n/messages";
import type { Workspace, WorkspacePresentation } from "@/lib/types";

export function getPresentation(workspace: Workspace | null): WorkspacePresentation | null {
  return workspace?.presentation ?? null;
}

export function displayGoal(workspace: Workspace, locale: Locale): string {
  const pres = getPresentation(workspace);
  if (pres?.goal) return pres.goal;
  return workspace.goal;
}

export function displayTaskObjective(
  workspace: Workspace,
  taskKey: string,
  fallback: string,
): string {
  const pres = getPresentation(workspace);
  return pres?.tasks?.[taskKey]?.objective || fallback;
}

export function displayTaskName(
  workspace: Workspace,
  taskKey: string,
  fallback: string,
): string {
  const pres = getPresentation(workspace);
  return pres?.tasks?.[taskKey]?.display_name || fallback;
}

export function displayWorkerName(
  workspace: Workspace,
  workerId: string,
  fallback: string,
): string {
  const pres = getPresentation(workspace);
  return pres?.workers?.[workerId]?.display_name || fallback;
}

export function displayWorkerTask(
  workspace: Workspace,
  workerId: string,
  fallback: string,
): string {
  const pres = getPresentation(workspace);
  return pres?.workers?.[workerId]?.assigned_task || fallback;
}

export function displayClaimStatement(
  workspace: Workspace,
  claimId: string,
  fallback: string,
): string {
  const pres = getPresentation(workspace);
  return pres?.claims?.[claimId]?.statement || fallback;
}

export function displayReport(workspace: Workspace) {
  const pres = getPresentation(workspace);
  const authoritative = workspace.report;
  if (pres?.report?.body_markdown) {
    return {
      title: pres.report.title || authoritative?.title || "Research Report",
      body: pres.report.body_markdown,
      localized: pres.report.is_localized ?? true,
    };
  }
  return {
    title: authoritative?.title || "Research Report",
    body: authoritative?.body_markdown || "",
    localized: false,
  };
}

export function dependsOnLabels(
  workspace: Workspace,
  dependsOn: string[],
  locale: Locale,
): string {
  if (!dependsOn.length) {
    return locale === "it" ? "Nessuna dipendenza" : "No dependencies";
  }
  const labels = dependsOn.map((key) => {
    const task = workspace.tasks.find((item) => item.task_key === key || item.id === key);
    if (!task) return key.replace(/_/g, " ");
    return displayTaskObjective(workspace, task.task_key, task.objective);
  });
  return labels.join(locale === "it" ? "; " : "; ");
}
