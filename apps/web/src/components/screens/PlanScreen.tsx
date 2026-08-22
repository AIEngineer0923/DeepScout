"use client";

import { useState } from "react";
import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { useT } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { displayTaskObjective, dependsOnLabels } from "@/presentation/demo";
import { useI18n } from "@/i18n/context";

export function PlanScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">{t("plan.loading")}</p>;
  const task = workspace.tasks.find((item) => item.id === selected) ?? workspace.tasks[0];
  const independent = workspace.tasks.filter((item) => item.depends_on.length === 0);
  const dependent = workspace.tasks.filter((item) => item.depends_on.length > 0);
  const completed = workspace.tasks.filter((item) => item.status === "completed").length;
  const running = workspace.tasks.filter((item) => item.status === "running").length;
  const pending = workspace.tasks.filter((item) => ["pending", "ready"].includes(item.status)).length;

  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-3">
        <section className="card compact">
          <h2>{t("plan.title", { count: workspace.tasks.length })}</h2>
          {workspace.tasks.map((item, index) => (
            <button key={item.id} type="button" className={`task-item ${task?.id === item.id ? "selected" : ""}`} onClick={() => setSelected(item.id)}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <strong className="wrap-text">
                  <span className="task-index">{index + 1}.</span>
                  {displayTaskObjective(workspace, item.task_key, item.objective)}
                </strong>
                <StatusBadge status={item.status} />
              </div>
              {!demoReadOnly ? <div className="muted">{item.display_name}</div> : null}
              <div className="muted">
                {t("plan.dependsOn", {
                  deps: dependsOnLabels(workspace, item.depends_on, locale),
                })}
              </div>
            </button>
          ))}
        </section>
        <section className="card compact">
          <div className="card-head">
            <h2>{t("plan.graph")}</h2>
          </div>
          <div className="dag-canvas">
            <div className="dag-goal">
              <strong>{t("plan.goal")}</strong>
              <div className="wrap-text">{workspace.goal}</div>
            </div>
            <div className="dag">
              <div className="dag-row">
                {independent.map((item, index) => (
                  <div key={item.id} className="dag-node">
                    <StatusBadge status={item.status} />
                    <div className="wrap-text">
                      <strong>
                        {index + 1}. {item.objective}
                      </strong>
                    </div>
                    <div className="muted">{item.display_name}</div>
                  </div>
                ))}
              </div>
              {dependent.length ? (
                <div className="dag-row">
                  {dependent.map((item, index) => (
                    <div key={item.id} className="dag-node">
                      <StatusBadge status={item.status} />
                      <div className="wrap-text">
                        <strong>
                          {independent.length + index + 1}. {item.objective}
                        </strong>
                      </div>
                      <div className="muted">{t("plan.dependsOn", { deps: item.depends_on.join(", ") })}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
          <div className="dag-legend">
            <span>
              <span className="dot ok" /> {t("phase.completed")}
            </span>
            <span>
              <span className="dot run" /> {t("phase.running")}
            </span>
            <span>
              <span className="dot muted" /> {t("phase.pending")}
            </span>
          </div>
        </section>
        <aside className="drawer">
          {task ? (
            <>
              <h2 className="wrap-text">{task.objective}</h2>
              <StatusBadge status={task.status} />
              <dl className="kv-list" style={{ marginTop: 12 }}>
                <div className="kv-row">
                  <dt>{t("table.worker")}</dt>
                  <dd>{task.display_name}</dd>
                </div>
                <div className="kv-row">
                  <dt>{t("plan.retries")}</dt>
                  <dd>{task.retries}</dd>
                </div>
                <div className="kv-row">
                  <dt>{t("workers.allowed")}</dt>
                  <dd>{task.allowed_tools.join(", ") || "—"}</dd>
                </div>
              </dl>
              <Link className="btn" style={{ width: "100%", marginTop: 12 }} href={`/research/${workspace.run_id}/workers`}>
                {t("plan.openWorker")} →
              </Link>
            </>
          ) : (
            <p className="empty">{t("plan.empty")}</p>
          )}
          <div className="panel-section">
            <h3>{t("plan.summary")}</h3>
            <dl className="kv-list">
              <div className="kv-row">
                <dt>{t("plan.total", { count: workspace.tasks.length })}</dt>
                <dd>{workspace.tasks.length}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("plan.completedCount", { count: completed })}</dt>
                <dd>{completed}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("plan.inProgress", { count: running })}</dt>
                <dd>{running}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("plan.pendingCount", { count: pending })}</dt>
                <dd>{pending}</dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>
    </div>
  );
}
