"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatCost, formatTokens } from "@/lib/format";
import { PhaseStepper } from "@/components/run/PhaseStepper";

export function MobileRunScreen() {
  const { workspace, reload } = useRun();
  if (!workspace) return <p className="empty">Loading…</p>;
  const worker = workspace.workers.find((item) => item.state === "running") ?? workspace.workers[0];
  return (
    <div className="grid">
      <h1 className="page-title wrap-text">{workspace.goal}</h1>
      <StatusBadge status={workspace.status} />
      <PhaseStepper completed={workspace.completed_phases} status={workspace.status} />
      {worker ? (
        <section className="card">
          <h2>Active worker</h2>
          <p>{worker.display_name}</p>
          <p className="wrap-text muted">{worker.assigned_task}</p>
        </section>
      ) : null}
      <section className="card">
        <h2>Progress</h2>
        <p>Sources {workspace.counts.sources} · Evidence {workspace.counts.evidence} · Claims {workspace.counts.claims}</p>
        <p>Tokens {formatTokens(workspace.usage.total_tokens)} · Cost {formatCost(workspace.usage.cost_usd, workspace.usage.cost_status)}</p>
      </section>
      <section className="card">
        <h2>Latest evidence</h2>
        {workspace.evidence.slice(-3).reverse().map((item) => (
          <p key={item.id} className="wrap-text">“{item.quote}”</p>
        ))}
      </section>
      <div className="grid">
        {["running", "pending"].includes(workspace.status) ? (
          <button className="btn danger" onClick={() => void api.cancel(workspace.run_id).then(reload)}>Cancel</button>
        ) : null}
        <Link className="btn" href={`/research/${workspace.run_id}/report`}>Open report</Link>
        <Link className="btn" href={`/research/${workspace.run_id}/sources`}>Sources</Link>
      </div>
    </div>
  );
}
