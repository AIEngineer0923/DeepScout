import type { Locale } from "./messages";

/** Privacy-safe default locale: Italy signals → IT, otherwise EN. */
export function detectLocaleFromAcceptLanguage(header: string | null): Locale {
  if (!header) return "en";
  for (const part of header.split(",")) {
    const token = part.split(";")[0]?.trim();
    if (!token) continue;
    const [lang, region] = token.split("-");
    if (region?.toUpperCase() === "IT") return "it";
    if (lang?.toLowerCase() === "it") return "it";
  }
  return "en";
}

export function detectLocaleFromNavigator(): Locale {
  if (typeof navigator === "undefined") return "en";
  const candidates = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const raw of candidates) {
    const token = raw.split(";")[0]?.trim();
    if (!token) continue;
    const [lang, region] = token.split("-");
    if (region?.toUpperCase() === "IT") return "it";
    if (lang?.toLowerCase() === "it") return "it";
  }
  return "en";
}
