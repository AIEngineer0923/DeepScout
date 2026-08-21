"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";

export function ClaimsScreen() {
  const { workspace } = useRun();
  const params = useSearchParams();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(params.get("claim"));
  if (!workspace) return <p className="empty">Loading claims…</p>;
  const filtered = useMemo(
    () => workspace.claims.filter((claim) => claim.statement.toLowerCase().includes(query.toLowerCase())),
    [workspace.claims, query],
  );
  const claim = filtered.find((item) => item.id === selected) ?? filtered[0];
  const evidence = workspace.evidence.filter((item) => item.claim_id === claim?.id);
  const summary = {
    total: workspace.claims.length,
    supported: workspace.claims.filter((c) => ["supported", "verified"].includes(c.verification_status)).length,
    partial: workspace.claims.filter((c) => c.verification_status.includes("partial")).length,
    contradicted: workspace.contradictions.length,
    pending: workspace.claims.filter((c) => c.verification_status === "pending").length,
  };
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-metrics">
        {Object.entries(summary).map(([key, value]) => (
          <article key={key} className="card metric"><div className="k">{key}</div><div className="v">{value}</div></article>
        ))}
      </div>
      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <section className="card">
          <input className="input" placeholder="Search claims..." value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data">
              <thead><tr><th>Claim</th><th>Status</th><th>Sources</th><th>Task</th></tr></thead>
              <tbody>
                {filtered.map((item, index) => (
                  <tr key={item.id} className={claim?.id === item.id ? "selected" : ""} onClick={() => setSelected(item.id)}>
                    <td className="wrap-text"><strong>C-{String(index + 1).padStart(2, "0")}</strong> {item.statement}</td>
                    <td><StatusBadge status={item.verification_status} /></td>
                    <td>{item.independent_source_count}</td>
                    <td>{item.task_key ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <aside className="drawer">
          {claim ? (
            <>
              <h2>Selected claim</h2>
              <StatusBadge status={claim.verification_status} />
              <p className="wrap-text">{claim.statement}</p>
              <p>Worker: {claim.worker_index ? `W${String(claim.worker_index).padStart(2, "0")}` : "—"}</p>
              <h3>Evidence</h3>
              {evidence.map((item) => (
                <article key={item.id} style={{ marginBottom: 12 }}>
                  <p className="wrap-text">“{item.quote}”</p>
                  {item.snapshot_id ? <Link href={`/research/${workspace.run_id}/snapshots/${item.snapshot_id}`}>Open snapshot</Link> : null}
                  {item.source_id ? <div><Link href={`/research/${workspace.run_id}/sources`}>Open source</Link></div> : null}
                </article>
              ))}
              <Link href={`/research/${workspace.run_id}/quality`}>Open in Quality / Contradictions →</Link>
            </>
          ) : <p className="empty">No claims yet.</p>}
        </aside>
      </div>
    </div>
  );
}
