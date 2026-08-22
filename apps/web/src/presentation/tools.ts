import type { Locale } from "@/i18n/messages";

const TOOL_LABELS: Record<string, Record<Locale, string>> = {
  web_search: { en: "Web search", it: "Ricerca web" },
  fetch_url: { en: "Fetch page", it: "Acquisizione pagina" },
  citation_audit: { en: "Citation check", it: "Verifica citazioni" },
  retrieve_evidence: { en: "Evidence retrieval", it: "Recupero evidenze" },
};

export function presentToolName(tool: string, locale: Locale): string {
  const key = tool.trim().toLowerCase();
  return TOOL_LABELS[key]?.[locale] ?? tool.replaceAll("_", " ");
}

export function presentToolList(tools: string[], locale: Locale): string {
  if (!tools.length) return "—";
  return tools.map((tool) => presentToolName(tool, locale)).join(", ");
}
