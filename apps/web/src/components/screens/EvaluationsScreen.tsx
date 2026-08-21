"use client";

import { useMemo, useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function EvaluationsScreen() {
  const { workspace } = useRun();
  const t = useT();
  const [query, setQuery] = useState("");
  const rows = useMemo(
    () =>
      workspace
        ? workspace.evaluations.filter((item) => `${item.evaluator_id} ${item.category}`.includes(query.toLowerCase()) || query === "")
        : [],
    [workspace, query],
  );
  if (!workspace) return <p className="empty">{t("evals.loading")}</p>;
  const groups = ["grounding", "quality", "security", "trajectory", "efficiency", "safety", "conversation", "image", "voice"];
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <p className="muted">{t("evals.note")}</p>
        <a className="btn" href={api.exportUrl(workspace.run_id, "evals-json")}>{t("action.exportEvals")} JSON</a>
        <a className="btn" href={api.exportUrl(workspace.run_id, "evals-csv")}>{t("action.exportEvals")} CSV</a>
      </div>
      <input className="input" placeholder={t("evals.filter")} value={query} onChange={(e) => setQuery(e.target.value)} />
      {groups.map((group) => {
        const items = rows.filter((item) => item.category === group);
        if (!items.length) return null;
        return (
          <section key={group} className="card" style={{ marginTop: 16 }}>
            <h2>{group}</h2>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>{t("table.evaluator")}</th>
                    <th>{t("table.method")}</th>
                    <th>{t("table.applicability")}</th>
                    <th>{t("table.result")}</th>
                  </tr>
                </thead>
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
