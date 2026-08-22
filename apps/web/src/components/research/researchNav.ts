export const RESEARCH_NAV = [
  { id: "live", suffix: "" },
  { id: "plan", suffix: "/plan" },
  { id: "workers", suffix: "/workers" },
  { id: "sources", suffix: "/sources" },
  { id: "snapshot", suffix: "/snapshots" },
  { id: "claims", suffix: "/claims" },
  { id: "quality", suffix: "/quality" },
  { id: "report", suffix: "/report" },
  { id: "evaluations", suffix: "/evaluations" },
] as const;

export type ResearchNavId = (typeof RESEARCH_NAV)[number]["id"];

export function researchHref(item: ResearchNavId, runId: string): string {
  if (item === "live") return `/research/${runId}`;
  if (item === "snapshot") return `/research/${runId}/snapshots`;
  return `/research/${runId}/${item}`;
}

export function isResearchNavCurrent(item: ResearchNavId, pathname: string, runId: string): boolean {
  if (item === "live") return pathname === `/research/${runId}`;
  if (item === "snapshot") return pathname.includes("/snapshots");
  return pathname.startsWith(`/research/${runId}/${item}`);
}
