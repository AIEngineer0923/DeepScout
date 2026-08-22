"use client";

import { useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { elapsed, formatTokens } from "@/lib/format";
import { workerProgress, workerTone } from "@/lib/visual";
import { useI18n, useT } from "@/i18n/context";
import { displayWorkerName, displayWorkerTask } from "@/presentation/demo";
import { presentWorkerHeadline, presentWorkerIndex } from "@/presentation/fields";

const DOWNSTREAM = ["extraction", "verification", "quality", "synthesis", "report"] as const;

function kindLabel(kind: string, t: (key: string) => string): string {
  if (kind.includes("llm") || kind.includes("agent") || kind.includes("langgraph")) return t("workers.agentic");
  return t("workers.deterministic");
}

export function WorkersScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">{t("workers.loading")}</p>;
  const worker = workspace.workers.find((item) => item.worker_id === selected) ?? workspace.workers[0];
  const arch = workspace.architecture;
  const runningCount = workspace.workers.filter((item) => item.state === "running").length;
  const completedCount = workspace.workers.filter((item) => item.state === "completed").length;

  return (
    <div>
      <RunHeader workspace={workspace} />
      <section className="card">
        <div className="card-head">
          <div>
            <h2>{t("workers.topology")}</h2>
            <p className="muted">{t("workers.topologyNote")}</p>
          </div>
        </div>
        <div className="topo-diagram">
          <div className="topo-col">
            {arch.orchestrator ? (
              <div className="topo-node completed">
                <strong>{arch.orchestrator.label}</strong>
                <span className="kind-tag deterministic">{kindLabel(arch.orchestrator.kind, t)}</span>
              </div>
            ) : null}
            <div className="topo-arrow">→</div>
            {arch.planner ? (
              <div className="topo-node running">
                <strong>{arch.planner.label}</strong>
                <span className="kind-tag agentic">{kindLabel(arch.planner.kind, t)}</span>
              </div>
            ) : null}
          </div>
          <div className="topo-col">
            <div className="topo-group">
              <div className="topo-group-label">
                {arch.workers?.label ?? t("workers.runtime", { count: workspace.workers.length })} ({workspace.workers.length})
              </div>
              {workspace.workers.map((item) => (
                <div key={item.worker_id} className={`topo-node ${item.state === "completed" ? "completed" : item.state === "running" ? "running" : ""}`}>
                  <strong>{presentWorkerHeadline(workspace, item.worker_id, locale)}</strong>
                  <div className="muted wrap-text">
                    {displayWorkerTask(workspace, item.worker_id, item.assigned_task)}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="topo-col">
            {DOWNSTREAM.map((key) => {
              const node = arch[key];
              if (!node) return null;
              return (
                <div key={key} className="topo-node">
                  <strong>{node.label}</strong>
                  <span className={`kind-tag ${node.kind.includes("llm") || node.kind.includes("agent") ? "agentic" : "deterministic"}`}>
                    {kindLabel(node.kind, t)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="topo-legend">
          <span>
            <span className="dot run" /> {t("phase.running")}
          </span>
          <span>
            <span className="dot ok" /> {t("phase.completed")}
          </span>
          <span>
            <span className="dot muted" /> {t("phase.pending")}
          </span>
        </div>
      </section>
      <div className="grid cols-2" style={{ marginTop: 18 }}>
        <section className="card">
          <div className="card-head">
            <div>
              <h2>{t("workers.runtime", { count: workspace.workers.length })}</h2>
              <p className="muted">{t("workers.runtimeNote")}</p>
            </div>
            <div className="row">
              <span className="chip">{t("workers.total", { count: workspace.workers.length })}</span>
              <span className="chip selected">{t("workers.runningCount", { count: runningCount })}</span>
              <span className="chip">{t("workers.completedCount", { count: completedCount })}</span>
            </div>
          </div>
          {workspace.workers.length === 0 ? <p className="empty">{t("workers.empty")}</p> : null}
          {workspace.workers.map((item) => {
            const pct = workerProgress(item.state, item.index);
            const tone = workerTone(item.index - 1);
            return (
              <button
                key={item.worker_id}
                type="button"
                className={`worker-card ${worker?.worker_id === item.worker_id ? "selected" : ""}`}
                onClick={() => setSelected(item.worker_id)}
              >
                <div className="row" style={{ alignItems: "flex-start" }}>
                  <span className={`worker-badge ${tone}`}>
                    {presentWorkerIndex(workspace, item.index, locale)}
                  </span>
                  <div className="grow">
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <strong>{presentWorkerHeadline(workspace, item.worker_id, locale)}</strong>
                      <StatusBadge status={item.state} />
                    </div>
                    <p className="wrap-text muted">
                      {displayWorkerTask(workspace, item.worker_id, item.assigned_task)}
                    </p>
                    <div className="progress-label">
                      <span>{t("phase.running")}</span>
                      <span>{pct}%</span>
                    </div>
                    <div className="progress">
                      <span className={item.state === "completed" ? "ok" : ""} style={{ width: `${pct}%` }} />
                    </div>
                    <div className="worker-stats">
                      <span>{item.agent_backed ? t("workers.agentic") : t("workers.deterministic")}</span>
                      <span>{t("plan.retries")}: {item.retries}</span>
                      <span>{elapsed(item.started_at)}</span>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </section>
        <aside className="drawer">
          {worker ? (
            <>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h2>{presentWorkerHeadline(workspace, worker.worker_id, locale)}</h2>
                <StatusBadge status={worker.state} />
              </div>
              <dl className="kv-list">
                <div className="kv-row">
                  <dt>{t("workers.assigned")}</dt>
                  <dd className="wrap-text">
                    {displayWorkerTask(workspace, worker.worker_id, worker.assigned_task)}
                  </dd>
                </div>
                <div className="kv-row">
                  <dt>{t("workers.parent")}</dt>
                  <dd>{worker.parent}</dd>
                </div>
                <div className="kv-row">
                  <dt>{t("table.status")}</dt>
                  <dd>
                    <StatusBadge status={worker.state} />
                  </dd>
                </div>
                <div className="kv-row">
                  <dt>{t("plan.retries")}</dt>
                  <dd>{worker.retries}</dd>
                </div>
              </dl>
              <div className="panel-section">
                <h3>{t("workers.configuration")}</h3>
                <dl className="kv-list">
                  <div className="kv-row">
                    <dt>{t("provider.model")}</dt>
                    <dd>{workspace.llm_model}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>{t("workers.kind")}</dt>
                    <dd>{worker.agent_backed ? t("workers.agentic") : t("workers.deterministic")}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>{t("workers.allowed")}</dt>
                    <dd>{worker.allowed_tools.join(", ") || "—"}</dd>
                    <dt>{t("workers.skills")}</dt>
                    <dd>{(worker.skills ?? []).join(", ") || "—"}</dd>
                  </div>
                </dl>
              </div>
              <div className="panel-section">
                <h3>{t("workers.metrics")}</h3>
                <dl className="kv-list">
                  <div className="kv-row">
                    <dt>{t("nav.sources")}</dt>
                    <dd>{workspace.counts.sources}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>{t("nav.snapshot")}</dt>
                    <dd>{workspace.counts.snapshots}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>{t("table.evidence")}</dt>
                    <dd>{workspace.counts.evidence}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>{t("provider.tokens")}</dt>
                    <dd>{formatTokens(workspace.usage.total_tokens, t("cost.unknown"))}</dd>
                  </div>
                </dl>
              </div>
              <p className="muted">{t("workers.prompt")}</p>
            </>
          ) : (
            <p className="empty">{t("workers.select")}</p>
          )}
        </aside>
      </div>
    </div>
  );
}
