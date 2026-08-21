"use client";

import { useMemo, useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { api } from "@/lib/api";

export function EvaluationsScreen() {
  const { workspace } = useRun();
  const [query, setQuery] = useState("");
  if (!workspace) return <p className="empty">Loading evaluations…</p>;
  const rows = useMemo(
    () => workspace.evaluations.filter((item) => `${item.evaluator_id} ${item.category}`.includes(query.toLowerCase()) || query === ""),
    [workspace.evaluations, query],
  );
  const groups = ["grounding", "quality", "security", "trajectory", "efficiency", "safety", "conversation", "image", "voice"];
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <p className="muted">Results come from the DeepScout evaluator registry. No aggregate vanity score is invented.</p>
        <a className="btn" href={api.exportUrl(workspace.run_id, "evals-json")}>Export evaluations</a>
      </div>
      <input className="input" placeholder="Filter evaluators..." value={query} onChange={(e) => setQuery(e.target.value)} />
      {groups.map((group) => {
        const items = rows.filter((item) => item.category === group);
        if (!items.length) return null;
        return (
          <section key={group} className="card" style={{ marginTop: 16 }}>
            <h2>{group}</h2>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Evaluator</th><th>Method</th><th>Applicability</th><th>Result</th></tr></thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.evaluator_id}>
                      <td>{item.description}<div className="muted">{item.evaluator_id} v{item.version}</div></td>
                      <td>{item.method.replaceAll("_", " ")}</td>
                      <td>{item.applicability.replaceAll("_", " ")}</td>
                      <td className="wrap-text">{item.value == null ? "—" : String(item.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
