"use client";

import { useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { elapsed, formatTokens } from "@/lib/format";
import type { Workspace } from "@/lib/types";
import { workerProgress, workerTone } from "@/lib/visual";
import { useI18n, useT } from "@/i18n/context";
import { presentArchitectureLabel, presentParentLabel } from "@/presentation/architecture";
import {
  presentWorkerCardTitle,
  presentWorkerFullTask,
  presentWorkerSecondarySummary,
} from "@/presentation/workers";
import { presentWorkerIndex } from "@/presentation/fields";
import { presentToolList } from "@/presentation/tools";

const DOWNSTREAM = ["extraction", "verification", "quality", "synthesis", "report"] as const;

function kindLabel(kind: string, t: (key: string) => string): string {
  if (kind.includes("llm") || kind.includes("agent") || kind.includes("langgraph")) return t("workers.agentic");
  return t("workers.deterministic");
}

function WorkerProgress({
  state,
  pct,
  t,
}: {
  state: string;
  pct: number;
  t: (key: string) => string;
}) {
  if (state === "completed") {
    return <p className="worker-state-note completed">{t("phase.completed")}</p>;
  }
  if (state === "failed") {
    return <p className="worker-state-note failed">{t("status.failed")}</p>;
  }
  if (state === "running" || state === "claimed") {
    return (
      <div className="worker-progress-block">
        <div className="progress-label">
          <span>{t("phase.running")}</span>
          <span>{pct}%</span>
        </div>
        <div className="progress">
          <span style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }
  return <p className="worker-state-note pending">{t("phase.pending")}</p>;
}

function WorkerCard({
  item,
  workspace,
  locale,
  selected,
  onSelect,
  t,
}: {
  item: Workspace["workers"][number];
  workspace: NonNullable<ReturnType<typeof useRun>["workspace"]>;
  locale: string;
  selected: boolean;
  onSelect: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  const tone = workerTone(item.index - 1);
  const title = presentWorkerCardTitle(workspace, item.worker_id, locale as "en" | "it");
  const summary = presentWorkerSecondarySummary(workspace, item.worker_id);
  const pct = workerProgress(item.state, item.index);

  return (
    <button
      type="button"
      className={`worker-card ${selected ? "selected" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="worker-card-header">
        <span className={`worker-badge ${tone}`}>{presentWorkerIndex(workspace, item.index, locale as "en" | "it")}</span>
        <StatusBadge status={item.state} />
      </div>
      <h3 className="worker-card-title">{title}</h3>
      {summary ? <p className="worker-card-summary">{summary}</p> : null}
      <WorkerProgress state={item.state} pct={pct} t={t} />
      <div className="worker-stats">
        <span>{item.agent_backed ? t("workers.agentic") : t("workers.deterministic")}</span>
        {item.retries > 0 ? <span>{t("plan.retries")}: {item.retries}</span> : null}
        {item.started_at ? <span>{elapsed(item.started_at)}</span> : null}
      </div>
    </button>
  );
}

export function WorkersScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  if (!workspace) return <p className="empty">{t("workers.loading")}</p>;

  const worker =
    workspace.workers.find((item) => item.worker_id === selected) ?? workspace.workers[0] ?? null;
  const arch = workspace.architecture;
  const runningCount = workspace.workers.filter((item) => item.state === "running").length;
  const completedCount = workspace.workers.filter((item) => item.state === "completed").length;

  return (
    <div className="workers-screen">
      <RunHeader workspace={workspace} />
      <section className="card workers-topology-card">
        <div className="card-head">
          <div>
            <h2>{t("workers.topology")}</h2>
            <p className="muted">{t("workers.topologyNote")}</p>
          </div>
        </div>
        <div className="topo-flow">
          <div className="topo-stage">
            <div className="topo-stage-label">{t("arch.orchestrator")}</div>
            <div className="topo-stage-row">
              {arch.orchestrator ? (
                <div className="topo-node topo-node-stage completed">
                  <span className="topo-node-title">
                    {presentArchitectureLabel("orchestrator", arch.orchestrator.label, t)}
                  </span>
                  <span className="kind-tag deterministic">{kindLabel(arch.orchestrator.kind, t)}</span>
                </div>
              ) : null}
              <span className="topo-arrow" aria-hidden="true">
                →
              </span>
              {arch.planner ? (
                <div className="topo-node topo-node-stage completed">
                  <span className="topo-node-title">
                    {presentArchitectureLabel("planner", arch.planner.label, t)}
                  </span>
                  <span className="kind-tag agentic">{kindLabel(arch.planner.kind, t)}</span>
                </div>
              ) : null}
            </div>
          </div>

          <div className="topo-stage topo-stage-workers">
            <div className="topo-stage-label">
              {t("workers.runtime", { count: workspace.workers.length })}
            </div>
            <div className="topo-workers-grid">
              {workspace.workers.map((item) => (
                <button
                  key={item.worker_id}
                  type="button"
                  className={`topo-node topo-node-worker ${item.state === "completed" ? "completed" : item.state === "running" ? "running" : ""} ${worker?.worker_id === item.worker_id ? "selected" : ""}`}
                  onClick={() => setSelected(item.worker_id)}
                >
                  <span className="topo-node-eyebrow">
                    {presentWorkerIndex(workspace, item.index, locale)}
                  </span>
                  <span className="topo-node-title">
                    {presentWorkerCardTitle(workspace, item.worker_id, locale)}
                  </span>
                  <StatusBadge status={item.state} />
                </button>
              ))}
            </div>
          </div>

          <div className="topo-stage">
            <div className="topo-stage-label">{t("phase.verify")}</div>
            <div className="topo-downstream-grid">
              {DOWNSTREAM.map((key) => {
                const node = arch[key];
                if (!node) return null;
                return (
                  <div key={key} className="topo-node topo-node-stage">
                    <span className="topo-node-title">
                      {presentArchitectureLabel(key, node.label, t)}
                    </span>
                    <span
                      className={`kind-tag ${node.kind.includes("llm") || node.kind.includes("agent") ? "agentic" : "deterministic"}`}
                    >
                      {kindLabel(node.kind, t)}
                    </span>
                  </div>
                );
              })}
            </div>
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

      <div className="workers-layout">
        <section className="card workers-list-card">
          <div className="card-head">
            <div>
              <h2>{t("workers.runtime", { count: workspace.workers.length })}</h2>
              <p className="muted">{t("workers.runtimeNote")}</p>
            </div>
            <div className="row">
              <span className="chip">{t("workers.total", { count: workspace.workers.length })}</span>
              {runningCount > 0 ? (
                <span className="chip selected">{t("workers.runningCount", { count: runningCount })}</span>
              ) : null}
              <span className="chip">{t("workers.completedCount", { count: completedCount })}</span>
            </div>
          </div>
          {workspace.workers.length === 0 ? <p className="empty">{t("workers.empty")}</p> : null}
          <div className="worker-card-list">
            {workspace.workers.map((item) => (
              <WorkerCard
                key={item.worker_id}
                item={item}
                workspace={workspace}
                locale={locale}
                selected={worker?.worker_id === item.worker_id}
                onSelect={() => setSelected(item.worker_id)}
                t={t}
              />
            ))}
          </div>
        </section>

        <aside className="drawer worker-detail">
          {worker ? (
            <>
              <div className="worker-detail-header">
                <span className={`worker-badge ${workerTone(worker.index - 1)}`}>
                  {presentWorkerIndex(workspace, worker.index, locale)}
                </span>
                <StatusBadge status={worker.state} />
              </div>
              <h2 className="worker-detail-title">
                {presentWorkerCardTitle(workspace, worker.worker_id, locale)}
              </h2>

              <div className="panel-section worker-detail-section">
                <h3>{t("workers.assigned")}</h3>
                <p className="worker-detail-task">
                  {presentWorkerFullTask(workspace, worker.worker_id, worker.assigned_task)}
                </p>
              </div>

              <dl className="kv-list">
                <div className="kv-row">
                  <dt>{t("workers.parent")}</dt>
                  <dd>{presentParentLabel(worker.parent, t)}</dd>
                </div>
                {worker.retries > 0 ? (
                  <div className="kv-row">
                    <dt>{t("plan.retries")}</dt>
                    <dd>{worker.retries}</dd>
                  </div>
                ) : null}
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
                    <dd>{presentToolList(worker.allowed_tools, locale)}</dd>
                  </div>
                  {worker.skills?.length ? (
                    <div className="kv-row">
                      <dt>{t("workers.skills")}</dt>
                      <dd>{worker.skills.join(", ")}</dd>
                    </div>
                  ) : null}
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
            </>
          ) : (
            <p className="empty">{t("workers.select")}</p>
          )}
        </aside>
      </div>
    </div>
  );
}
