"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { ExternalLink } from "@/components/ExternalLink";
import { api } from "@/lib/api";

export function SourcesScreen() {
  const { workspace } = useRun();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">Loading sources…</p>;
  const filtered = useMemo(() => {
    return workspace.sources.filter((source) => {
      const hay = `${source.title} ${source.domain} ${source.url}`.toLowerCase();
      const matchesQuery = hay.includes(query.toLowerCase());
      const matchesStatus = status === "all" || source.fetch_state === status;
      return matchesQuery && matchesStatus;
    });
  }, [workspace.sources, query, status]);
  const source = filtered.find((item) => item.id === selected) ?? filtered[0];
  const stats = {
    discovered: workspace.sources.length,
    fetched: workspace.sources.filter((s) => s.fetch_state === "fetched").length,
    snapshots: workspace.counts.snapshots,
    claims: workspace.counts.claims,
    evidence: workspace.counts.evidence,
  };
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Sources</h2>
          <p className="muted">All sources discovered and processed during this research.</p>
        </div>
        <a className="btn" href={api.exportUrl(workspace.run_id, "sources-csv")}>Export sources</a>
      </div>
      <div className="grid cols-metrics" style={{ margin: "12px 0" }}>
        {Object.entries(stats).map(([key, value]) => (
          <article key={key} className="card metric"><div className="k">{key}</div><div className="v">{value}</div></article>
        ))}
      </div>
      <div className="grid cols-2">
        <section className="card">
          <div className="toolbar">
            <input className="input grow" placeholder="Search by title, domain or URL..." value={query} onChange={(e) => setQuery(e.target.value)} />
            <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">All status</option>
              <option value="fetched">Fetched</option>
              <option value="discovered">Discovered</option>
            </select>
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Source</th><th>Status</th><th>Worker</th><th>Claims</th><th>Evidence</th></tr></thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className={source?.id === item.id ? "selected" : ""} onClick={() => setSelected(item.id)}>
                    <td>
                      <div className="wrap-text"><strong>{item.title}</strong></div>
                      <div className="muted">{item.domain}</div>
                    </td>
                    <td><StatusBadge status={item.fetch_state} /></td>
                    <td>{item.worker_index ? `W${String(item.worker_index).padStart(2, "0")}` : "—"}</td>
                    <td>{item.claim_count}</td>
                    <td>{item.evidence_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <aside className="drawer">
          {source ? (
            <>
              <h2 className="wrap-text">{source.title}</h2>
              <StatusBadge status={source.fetch_state} />
              <p><ExternalLink href={source.url}>{source.url}</ExternalLink></p>
              <p>Type: {source.source_type}</p>
              <p>Snapshot: {source.snapshot_available ? "Available" : "Not yet"}</p>
              {source.task_id ? <p>Task: {source.task_key}</p> : null}
              {source.worker_index ? <Link href={`/research/${workspace.run_id}/workers`}>Open worker W{String(source.worker_index).padStart(2, "0")}</Link> : null}
              {source.snapshot_id ? (
                <Link className="btn" href={`/research/${workspace.run_id}/snapshots/${source.snapshot_id}`}>View snapshot</Link>
              ) : null}
              <Link href={`/research/${workspace.run_id}/claims`}>Claims / evidence →</Link>
            </>
          ) : <p className="empty">No sources yet.</p>}
        </aside>
      </div>
    </div>
  );
}
