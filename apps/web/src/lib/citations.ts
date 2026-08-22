import type { Workspace } from "@/lib/types";
import { safeHttpUrl } from "@/lib/safe-url";

export type CitationTarget = {
  sourceId: string;
  title: string;
  url: string;
};

export function buildCitationMap(
  markdown: string,
  sources: Workspace["sources"],
): Record<number, CitationTarget> {
  const map: Record<number, CitationTarget> = {};
  const byUrl = new Map<string, Workspace["sources"][number]>();
  for (const source of sources) {
    const safe = safeHttpUrl(source.url);
    if (safe) byUrl.set(safe, source);
  }

  const bibliography = markdown.match(/##\s+Sources Cited[\s\S]*$/i)?.[0] ?? "";
  const linePattern = /^\s*[-*]?\s*\[(\d{1,2})\]\s*(.+)$/gm;
  for (const match of bibliography.matchAll(linePattern)) {
    const index = Number(match[1]);
    const rest = match[2].trim();
    const urlMatch = rest.match(/(https?:\/\/\S+)/i);
    const url = urlMatch ? safeHttpUrl(urlMatch[1]) : null;
    const matched = url ? byUrl.get(url) : undefined;
    const source = matched ?? sources[index - 1];
    if (!source || map[index]) continue;
    map[index] = { sourceId: source.id, title: source.title, url: source.url };
  }

  sources.forEach((source, offset) => {
    const index = offset + 1;
    if (!map[index]) {
      map[index] = { sourceId: source.id, title: source.title, url: source.url };
    }
  });

  return map;
}

export function linkifyNumericCitations(
  markdown: string,
  runId: string,
  citations: Record<number, CitationTarget>,
): string {
  const chunks = markdown.split(/(```[\s\S]*?```)/g);
  return chunks
    .map((chunk) => {
      if (chunk.startsWith("```")) return chunk;
      return chunk.replace(/\[(\d{1,2})\](?!\()/g, (match, rawIndex: string) => {
        const index = Number(rawIndex);
        const target = citations[index];
        if (!target) return match;
        return `[${index}](/research/${runId}/sources/${target.sourceId})`;
      });
    })
    .join("");
}
