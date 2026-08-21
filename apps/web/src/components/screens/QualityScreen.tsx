"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";

export function QualityScreen() {
  const { workspace } = useRun();
  if (!workspace) return <p className="empty">Loading quality…</p>;
  const claimById = Object.fromEntries(workspace.claims.map((claim) => [claim.id, claim]));
  const deterministic = workspace.evaluations.filter((item) => item.method === "deterministic_code");
  return (
    <div>
      <RunHeader workspace={workspace} />
      <section className="card">
        <h2>Quality checks</h2>
        <p className="muted">No vanity overall score. These are deterministic evaluator results for this run.</p>
        <div className="grid cols-metrics">
          {deterministic.slice(0, 6).map((item) => (
            <article key={item.evaluator_id} className="metric">
              <div className="k">{item.evaluator_id.replaceAll("_", " ")}</div>
              <div className="v" style={{ fontSize: 16 }}>{item.value == null ? "n/a" : String(item.value)}</div>
            </article>
          ))}
        </div>
      </section>
      <section className="card" style={{ marginTop: 16 }}>
        <h2>Contradictions ({workspace.contradictions.length})</h2>
        {workspace.contradictions.length === 0 ? <p className="empty">No contradictions recorded.</p> : null}
        {workspace.contradictions.map((item) => (
          <article key={item.id} className="card" style={{ marginBottom: 12 }}>
            <StatusBadge status={item.evidence_status} />
            <p className="wrap-text">{item.description}</p>
            <p>Claims: {claimById[item.claim_a_id]?.statement ?? item.claim_a_id} · {claimById[item.claim_b_id]?.statement ?? item.claim_b_id}</p>
            <Link href={`/research/${workspace.run_id}/claims`}>Inspect claims</Link>
          </article>
        ))}
      </section>
    </div>
  );
}
