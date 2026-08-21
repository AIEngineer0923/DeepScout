"use client";

import { useState } from "react";
import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";

export function PlanScreen() {
  const { workspace } = useRun();
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">Loading plan…</p>;
  const task = workspace.tasks.find((item) => item.id === selected) ?? workspace.tasks[0];
  const independent = workspace.tasks.filter((item) => item.depends_on.length === 0);
  const dependent = workspace.tasks.filter((item) => item.depends_on.length > 0);
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-3">
        <section className="card">
          <h2>Research plan ({workspace.tasks.length} tasks)</h2>
          {workspace.tasks.map((item) => (
            <button key={item.id} type="button" className={`mode ${task?.id === item.id ? "selected" : ""}`} onClick={() => setSelected(item.id)}>
              <strong className="wrap-text">{item.objective}</strong>
              <div className="muted">{item.display_name} · depends on {item.depends_on.join(", ") || "none"}</div>
              <StatusBadge status={item.status} />
            </button>
          ))}
        </section>
        <section className="card">
          <h2>Task dependency graph</h2>
          <p className="wrap-text muted">Research goal: {workspace.goal}</p>
          <div className="dag">
            <div className="dag-row">
              {independent.map((item) => (
                <div key={item.id} className="dag-node">
                  <StatusBadge status={item.status} />
                  <div className="wrap-text"><strong>{item.objective}</strong></div>
                  <div className="muted">{item.display_name}</div>
                </div>
              ))}
            </div>
            {dependent.length ? (
              <div className="dag-row">
                {dependent.map((item) => (
                  <div key={item.id} className="dag-node">
                    <StatusBadge status={item.status} />
                    <div className="wrap-text"><strong>{item.objective}</strong></div>
                    <div className="muted">Depends on {item.depends_on.join(", ")}</div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </section>
        <aside className="drawer">
          {task ? (
            <>
              <h2 className="wrap-text">{task.objective}</h2>
              <StatusBadge status={task.status} />
              <p>Worker: {task.display_name}</p>
              <p>Retries: {task.retries}</p>
              <p>Tools: {task.allowed_tools.join(", ") || "—"}</p>
              <Link className="btn" href={`/research/${workspace.run_id}/workers`}>Open worker details →</Link>
            </>
          ) : (
            <p className="empty">No tasks yet.</p>
          )}
          <div style={{ marginTop: 16 }}>
            <h3>Plan summary</h3>
            <p>Total {workspace.tasks.length}</p>
            <p>Completed {workspace.tasks.filter((t) => t.status === "completed").length}</p>
            <p>In progress {workspace.tasks.filter((t) => t.status === "running").length}</p>
            <p>Pending {workspace.tasks.filter((t) => t.status === "pending" || t.status === "ready").length}</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
