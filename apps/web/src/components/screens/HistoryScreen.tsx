"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatCost, formatTokens, relativeTime } from "@/lib/format";
import type { RunListItem } from "@/lib/types";
import { StatusBadge } from "../StatusBadge";

export function HistoryScreen() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const limit = 8;

  useEffect(() => {
    api.listRuns({ status: status || undefined, q: q || undefined, limit, offset }).then((data) => {
      setRows(data.items);
      setTotal(data.total);
    }).catch(() => undefined);
  }, [status, q, offset]);

  return (
    <div>
      <h1 className="page-title">History</h1>
      <p className="page-sub">View and manage past research runs.</p>
      <div className="tabs">
        {["", "completed", "failed", "cancelled"].map((item) => (
          <button key={item || "all"} className={`tab ${status === item ? "active" : ""}`} onClick={() => { setStatus(item); setOffset(0); }}>
            {item || "All runs"}
          </button>
        ))}
      </div>
      <div className="toolbar">
        <input className="input grow" placeholder="Search research runs..." value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} />
        <a className="btn" href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/research-runs?limit=100`}>Open JSON</a>
      </div>
      <section className="card">
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Research</th><th>Status</th><th>Stages</th><th>Duration</th><th>Tokens</th><th>Cost</th><th>Updated</th></tr></thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.id}>
                  <td className="wrap-text"><Link href={`/research/${run.id}`}>{run.goal}</Link><div className="mono muted">{run.id}</div></td>
                  <td><StatusBadge status={run.status} /></td>
                  <td>{run.completed_task_count}/{run.task_count}</td>
                  <td>{relativeTime(run.started_at)}</td>
                  <td>{formatTokens(run.total_tokens)}</td>
                  <td>{formatCost(run.cost_usd, run.cost_status)}</td>
                  <td>{relativeTime(run.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row" style={{ justifyContent: "space-between", marginTop: 12 }}>
          <span className="muted">Showing {rows.length} of {total}</span>
          <div className="row">
            <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button>
            <button className="btn" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Next</button>
          </div>
        </div>
      </section>
    </div>
  );
}
