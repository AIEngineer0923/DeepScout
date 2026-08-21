"use client";

import { useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { useT } from "@/i18n/context";

export function WorkersScreen() {
  const { workspace } = useRun();
  const t = useT();
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">{t("workers.loading")}</p>;
  const worker = workspace.workers.find((item) => item.worker_id === selected) ?? workspace.workers[0];
  const arch = workspace.architecture;
  return (
    <div>
      <RunHeader workspace={workspace} />
      <section className="card">
        <h2>{t("workers.topology")}</h2>
        <p className="muted">{t("workers.topologyNote")}</p>
        <div className="topo">
          {Object.entries(arch).map(([key, node]) => (
            <div key={key} className="topo-node">
              <strong>{node.label}</strong>
              <div className="muted">{node.kind.replaceAll("_", " ")}</div>
            </div>
          ))}
        </div>
      </section>
      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <section className="card">
          <h2>{t("workers.runtime", { count: workspace.workers.length })}</h2>
          {workspace.workers.length === 0 ? <p className="empty">{t("workers.empty")}</p> : null}
          {workspace.workers.map((item) => (
            <button key={item.worker_id} type="button" className={`mode ${worker?.worker_id === item.worker_id ? "selected" : ""}`} onClick={() => setSelected(item.worker_id)}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{item.display_name}</strong>
                <StatusBadge status={item.state} />
              </div>
              <p className="wrap-text muted">{item.assigned_task}</p>
              <p className="mono muted">{item.worker_id}</p>
            </button>
          ))}
        </section>
        <aside className="drawer">
          {worker ? (
            <>
              <h2>{worker.display_name}</h2>
              <p>
                {t("workers.id")}: <span className="mono">{worker.worker_id}</span>
              </p>
              <p>{t("workers.role")}</p>
              <p>{t("workers.parent")}: {worker.parent}</p>
              <p>{t("workers.assigned")}: <span className="wrap-text">{worker.assigned_task}</span></p>
              <p>{t("workers.allowed")}: {worker.allowed_tools.join(", ")}</p>
              <p>{t("plan.retries")}: {worker.retries}</p>
              <p>{t("workers.prompt")}</p>
            </>
          ) : (
            <p className="empty">{t("workers.select")}</p>
          )}
        </aside>
      </div>
    </div>
  );
}
