import type { Locale } from "@/i18n/messages";

/**
 * Contradiction descriptions arrive from the research runtime as
 * `"<Kind>: <detail>"`, where `<Kind>` comes from a closed set defined in
 * `libs/research/src/deepscout_research/phases/contradiction.py`. The English
 * text is already product copy, so it is rendered as-is; Italian is mapped per
 * kind. `contradictions.test.ts` pins the two sets together.
 */
export const CONTRADICTION_KINDS = [
  "Timeframe difference",
  "Scope difference",
  "Methodological difference",
  "Negation conflict",
  "Opposing values",
] as const;

export type ContradictionKind = (typeof CONTRADICTION_KINDS)[number];

const IT_KIND: Record<ContradictionKind, string> = {
  "Timeframe difference": "Differenza temporale",
  "Scope difference": "Differenza di ambito",
  "Methodological difference": "Differenza metodologica",
  "Negation conflict": "Conflitto di negazione",
  "Opposing values": "Valori opposti",
};

const IT_DETAIL: Array<[RegExp, (m: RegExpMatchArray) => string]> = [
  [/^only one claim is scoped to (.+)$/, (m) => `solo una delle affermazioni è riferita a ${m[1]}`],
  [/^the claims differ on (.+)$/, (m) => `le affermazioni differiscono su ${m[1]}`],
  [/^one claim asserts what the other denies$/, () => "un'affermazione sostiene ciò che l'altra nega"],
  [
    /^(.+) versus (.+) on a comparable proposition$/,
    (m) => `${m[1]} contro ${m[2]} su una proposizione comparabile`,
  ],
];

function splitDescription(description: string): { kind: ContradictionKind; detail: string } | null {
  for (const kind of CONTRADICTION_KINDS) {
    const prefix = `${kind}: `;
    if (description.startsWith(prefix)) {
      return { kind, detail: description.slice(prefix.length) };
    }
  }
  return null;
}

/** Kind alone, for a badge or grouping header. Null when the shape is unknown. */
export function contradictionKindLabel(description: string, locale: Locale): string | null {
  const parsed = splitDescription(description);
  if (!parsed) return null;
  return locale === "it" ? IT_KIND[parsed.kind] : parsed.kind;
}

/** Full sentence for display. Unrecognised descriptions pass through unchanged. */
export function presentContradiction(description: string, locale: Locale): string {
  const parsed = splitDescription(description);
  if (!parsed) return description;
  if (locale !== "it") return description;
  for (const [pattern, render] of IT_DETAIL) {
    const match = parsed.detail.match(pattern);
    if (match) return `${IT_KIND[parsed.kind]}: ${render(match)}`;
  }
  return `${IT_KIND[parsed.kind]}: ${parsed.detail}`;
}
