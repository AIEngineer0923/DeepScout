import type { Locale } from "@/i18n/messages";
import type { Workspace } from "@/lib/types";
import { displayGoal, getPresentation } from "@/presentation/demo";

const DEFAULT_TITLE_LENGTH = 80;

export function normalizeResearchText(value: string): string {
  return value
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim().replace(/^#{1,6}\s+/, "").replace(/^[-*•]\s+/, ""))
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

export function compactResearchTitle(value: string, maxLength = DEFAULT_TITLE_LENGTH): string {
  const normalized = normalizeResearchText(value);
  if (normalized.length <= maxLength) return normalized;

  const slice = normalized.slice(0, Math.max(1, maxLength - 1));
  const lastWord = slice.lastIndexOf(" ");
  const boundary = lastWord >= Math.floor(maxLength * 0.58) ? lastWord : slice.length;
  return `${slice.slice(0, boundary).replace(/[,:;\-–—]+$/u, "").trimEnd()}…`;
}

export function displayResearchTitle(workspace: Workspace, locale: Locale): string {
  const presentation = getPresentation(workspace);
  const candidate = presentation?.title || displayGoal(workspace, locale);
  return compactResearchTitle(candidate);
}
