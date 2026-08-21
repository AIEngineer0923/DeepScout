import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { DashboardScreen } from "@/components/screens/DashboardScreen";
import type { Overview } from "@/lib/types";

const EMPTY: Overview = {
  active: null,
  recent: [],
  totals: {
    runs: 0,
    sources: 0,
    evidence: 0,
    claims: 0,
    known_cost_usd: null,
    cost_status: "unknown",
    avg_completion_seconds: null,
  },
  identity: { label: "Local workspace", role: "Operator" },
  langsmith: { connected: false, project: "deepscout-dev", region: "EU", tracing: false },
  providers: {},
};

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ run?: string }>;
}) {
  const params = await searchParams;
  if (params.run) redirect(`/research/${params.run}`);
  let overview = EMPTY;
  try {
    overview = await api.overview();
  } catch {
    overview = EMPTY;
  }
  return <DashboardScreen overview={overview} />;
}
