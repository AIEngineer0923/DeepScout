export const COUNTRY_OPTIONS = [
  { code: "IT", en: "Italy", it: "Italia" },
  { code: "US", en: "United States", it: "Stati Uniti" },
  { code: "GB", en: "United Kingdom", it: "Regno Unito" },
  { code: "DE", en: "Germany", it: "Germania" },
  { code: "FR", en: "France", it: "Francia" },
  { code: "ES", en: "Spain", it: "Spagna" },
  { code: "EU", en: "Europe", it: "Europa" },
  { code: "GLOBAL", en: "Global", it: "Globale" },
] as const;

export function countryLabel(code: string, locale: "en" | "it"): string {
  const row = COUNTRY_OPTIONS.find((item) => item.code === code || item.en === code);
  if (!row) return code;
  return locale === "it" ? row.it : row.en;
}
