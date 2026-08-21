"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { elapsed, formatCost, formatTokens, relativeTime } from "@/lib/format";
import type { Overview } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export function DashboardScreen({ overview }: { overview: Overview }) {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const active = overview.active;

  async function start() {
    if (!goal.trim()) return;
    setBusy(true);
    try {
      const created = await api.createRun({ goal: goal.trim(), research_mode: "standard" });
      await api.execute(created.id);
      router.push(`/research/${created.id}`);
    } finally {
      setBusy(false);
    }
  }

  const metrics = useMemo(
    () => [
      { k: "Researches", v: String(overview.totals.runs) },
      { k: "Sources analyzed", v: String(overview.totals.sources) },
      { k: "Evidence collected", v: String(overview.totals.evidence) },
      { k: "Claims", v: String(overview.totals.claims) },
      { k: "Avg. completion", v: overview.totals.avg_completion_seconds ? `${Math.round(overview.totals.avg_completion_seconds / 60)}m` : "—" },
      { k: "Total estimated cost", v: formatCost(overview.totals.known_cost_usd, overview.totals.cost_status) },
    ],
    [overview],
  );

  return (
    <div className="grid" style={{ gap: 20 }}>
      <div>
        <h1 className="page-title">Welcome back</h1>
        <p className="page-sub">Start a research goal or inspect an active run. Content is always taken from the current ResearchRun.</p>
      </div>
      <div className="grid cols-2">
        <section className="card">
          <label htmlFor="quick-goal">Research goal</label>
          <textarea id="quick-goal" className="textarea" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Ask anything. Be specific for better results..." />
          <div className="row" style={{ marginTop: 12, justifyContent: "space-between" }}>
            <span className="muted">Standard · Automatic models</span>
            <button className="btn primary" disabled={busy || !goal.trim()} onClick={() => void start()}>Start research →</button>
          </div>
        </section>
        <section className="card">
          <h2>Active research</h2>
          {active ? (
            <>
              <p className="wrap-text"><strong>{active.goal}</strong></p>
              <StatusBadge status={active.status} />
              <p className="muted">Started {elapsed(active.started_at ?? active.created_at)}</p>
              <p className="muted">{active.task_count} tasks · {active.source_count} sources · {active.evidence_count} evidence</p>
              <Link className="btn" href={`/research/${active.id}`}>Open research →</Link>
            </>
          ) : (
            <p className="empty">No active research. Start a new goal to begin.</p>
          )}
        </section>
      </div>
      <div className="grid cols-metrics">
        {metrics.map((metric) => (
          <article key={metric.k} className="card metric">
            <div className="k">{metric.k}</div>
            <div className="v">{metric.v}</div>
          </article>
        ))}
      </div>
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Recent research</h2>
          <Link href="/history">View history</Link>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>Research</th><th>Status</th><th>Sources</th><th>Evidence</th><th>Tokens</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {overview.recent.length === 0 ? (
                <tr><td colSpan={6} className="empty">No runs yet.</td></tr>
              ) : overview.recent.map((run) => (
                <tr key={run.id}>
                  <td><Link href={`/research/${run.id}`} className="wrap-text">{run.goal}</Link></td>
                  <td><StatusBadge status={run.status} /></td>
                  <td>{run.source_count}</td>
                  <td>{run.evidence_count}</td>
                  <td>{formatTokens(run.total_tokens)}</td>
                  <td>{relativeTime(run.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
