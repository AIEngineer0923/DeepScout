"use client";

import { useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";

export function WorkersScreen() {
  const { workspace } = useRun();
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">Loading workers…</p>;
  const worker = workspace.workers.find((item) => item.worker_id === selected) ?? workspace.workers[0];
  const arch = workspace.architecture;
  return (
    <div>
      <RunHeader workspace={workspace} />
      <section className="card">
        <h2>Agent topology</h2>
        <p className="muted">Labels match the real runtime: deterministic engines are not shown as LLM agents.</p>
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
          <h2>Runtime workers ({workspace.workers.length})</h2>
          {workspace.workers.length === 0 ? <p className="empty">Workers appear when the planner creates tasks.</p> : null}
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
              <p>Worker ID: <span className="mono">{worker.worker_id}</span></p>
              <p>Role: Research worker (search graph, not a hidden LLM)</p>
              <p>Parent: {worker.parent}</p>
              <p>Assigned task: <span className="wrap-text">{worker.assigned_task}</span></p>
              <p>Allowed tools: {worker.allowed_tools.join(", ")}</p>
              <p>Retries: {worker.retries}</p>
              <p>Prompt: research_worker v1 is registered; this worker path is search/fetch, not a model call.</p>
            </>
          ) : (
            <p className="empty">Select a worker.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
