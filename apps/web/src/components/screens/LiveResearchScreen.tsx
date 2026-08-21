"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { formatCost, formatTokens, relativeTime } from "@/lib/format";

export function LiveResearchScreen() {
  const { workspace, error } = useRun();
  if (error) return <p className="badge bad">{error}</p>;
  if (!workspace) return <p className="empty">Loading research…</p>;
  const running = workspace.workers.filter((w) => ["running", "claimed", "ready"].includes(w.state));
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-3">
        <section className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Research plan ({workspace.tasks.length} tasks)</h2>
            <Link href={`/research/${workspace.run_id}/plan`}>DAG view</Link>
          </div>
          {workspace.tasks.map((task) => (
            <article key={task.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--ds-line)" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong className="wrap-text">{task.objective}</strong>
                <StatusBadge status={task.status} />
              </div>
              <div className="muted">{task.display_name}</div>
            </article>
          ))}
        </section>
        <section className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Active workers ({running.length})</h2>
            <Link href={`/research/${workspace.run_id}/workers`}>View all workers</Link>
          </div>
          {workspace.workers.map((worker) => (
            <article key={worker.worker_id} style={{ padding: "10px 0", borderBottom: "1px solid var(--ds-line)" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{worker.display_name}</strong>
                <StatusBadge status={worker.state} />
              </div>
              <p className="wrap-text muted">{worker.assigned_task}</p>
            </article>
          ))}
        </section>
        <aside className="card">
          <h2>Research overview</h2>
          <p>Provider: {workspace.llm_provider}</p>
          <p>Model: {workspace.llm_model}</p>
          <p>Max sources: {workspace.budget.max_sources}</p>
          <p>Max iterations: {workspace.budget.max_iterations}</p>
          <p>Sources: {workspace.counts.sources}</p>
          <p>Snapshots: {workspace.counts.snapshots}</p>
          <p>Claims: {workspace.counts.claims}</p>
          <p>Evidence: {workspace.counts.evidence}</p>
          <p>Contradictions: {workspace.counts.contradictions}</p>
          <p>Tokens: {formatTokens(workspace.usage.total_tokens)}</p>
          <p>Application cost: {formatCost(workspace.usage.cost_usd, workspace.usage.cost_status)}</p>
          <p>Evaluation cost: {formatCost(workspace.usage.evaluation_cost_usd, workspace.usage.evaluation_cost_usd == null ? "unknown" : "estimated")}</p>
        </aside>
      </div>
      <section className="card" style={{ marginTop: 16 }}>
        <h2>Live activity</h2>
        {workspace.activity.slice(-12).reverse().map((event) => (
          <div key={event.sequence} className="row" style={{ justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #f3f4f6" }}>
            <span className="wrap-text">{event.type}</span>
            <span className="muted">{relativeTime(event.created_at)}</span>
          </div>
        ))}
        {workspace.activity.length === 0 ? <p className="empty">Waiting for events.</p> : null}
      </section>
    </div>
  );
}
