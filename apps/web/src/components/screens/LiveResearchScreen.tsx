"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { workerProgress } from "@/lib/visual";
import { useI18n } from "@/i18n/context";
import { MobileRunScreen } from "@/components/screens/MobileRunScreen";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { ResearchTimeline } from "@/components/demo/ResearchTimeline";
import {
  displayTaskObjective,
  displayWorkerName,
  displayWorkerTask,
} from "@/presentation/demo";
import { vocab } from "@/presentation/vocabulary";

export function LiveResearchScreen() {
  const { workspace, error } = useRun();
  const { t, locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  if (error) return <p className="badge bad">{error}</p>;
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  const running = workspace.workers.filter((w) => ["running", "claimed", "ready"].includes(w.state));
  const completed = ["completed", "failed", "cancelled"].includes(workspace.status);

  return (
    <div className="live-research-page">
      <div className="live-page-header">
        <RunHeader workspace={workspace} />
      </div>
      <MobileRunScreen />
      <div className="grid cols-live live-desktop">
        <section className="card compact">
          <div className="card-head">
            <h2>{t("live.plan", { count: workspace.tasks.length })}</h2>
            <Link className="link-btn" href={`/research/${workspace.run_id}/plan`}>
              {t("live.dagView")} →
            </Link>
          </div>
          {workspace.tasks.map((task, index) => (
            <article key={task.id} className="list-row">
              <div className="grow">
                <strong className="wrap-text task-title">
                  <span className="task-index">{index + 1}.</span>
                  {displayTaskObjective(workspace, task.task_key, task.objective)}
                </strong>
              </div>
              <StatusBadge status={task.status} />
            </article>
          ))}
        </section>
        <section className="card compact">
          <div className="card-head">
            <h2>
              {demoReadOnly
                ? t("demo.agentsActive", { count: running.length })
                : t("live.workers", { count: running.length })}
            </h2>
            <Link className="link-btn" href={`/research/${workspace.run_id}/workers`}>
              {t("live.viewWorkers")} →
            </Link>
          </div>
          {workspace.workers.map((worker) => {
            const pct = workerProgress(worker.state, worker.index);
            return (
              <article key={worker.worker_id} className="list-row worker-row">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong className="wrap-text">
                    {displayWorkerName(workspace, worker.worker_id, worker.display_name)}
                  </strong>
                  <StatusBadge status={worker.state} />
                </div>
                <p className="wrap-text muted">{displayWorkerTask(workspace, worker.worker_id, worker.assigned_task)}</p>
                {!completed ? (
                  <>
                    <div className="progress-label">
                      <span>{t("phase.running")}</span>
                      <span>{pct}%</span>
                    </div>
                    <div className="progress">
                      <span className={worker.state === "completed" ? "ok" : ""} style={{ width: `${pct}%` }} />
                    </div>
                  </>
                ) : null}
              </article>
            );
          })}
        </section>
        <aside className="drawer overview-drawer">
          <h2>{t("live.overview")}</h2>
          <dl className="kv-list">
            <div className="kv-row">
              <dt>{t("new.step2")}</dt>
              <dd>{workspace.research_mode ?? "—"}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.outputLanguage")}</dt>
              <dd>{workspace.output_language ?? "—"}</dd>
            </div>
          </dl>
          <div className="panel-section">
            <h3>{completed ? t("demo.resultsSummary") : t("live.progress")}</h3>
            <dl className="kv-list">
              <div className="kv-row">
                <dt>{vocab("source", locale)}</dt>
                <dd>{workspace.counts.sources}</dd>
              </div>
              <div className="kv-row">
                <dt>{vocab("snapshot", locale)}</dt>
                <dd>{workspace.counts.snapshots}</dd>
              </div>
              <div className="kv-row">
                <dt>{vocab("claim", locale)}</dt>
                <dd>{workspace.counts.claims}</dd>
              </div>
              <div className="kv-row">
                <dt>{vocab("evidence", locale)}</dt>
                <dd>{workspace.counts.evidence}</dd>
              </div>
              <div className="kv-row">
                <dt>{vocab("contradiction", locale)}</dt>
                <dd>{workspace.counts.contradictions}</dd>
              </div>
            </dl>
          </div>
          {!demoReadOnly ? (
            <div className="panel-section">
              <h3>{t("live.quickActions")}</h3>
              <div className="grid" style={{ gap: 8 }}>
                <Link className="btn" href={`/research/${workspace.run_id}/workers`}>
                  {t("live.viewWorkers")}
                </Link>
                <Link className="btn" href={`/research/${workspace.run_id}/sources`}>
                  {t("nav.sources")}
                </Link>
              </div>
            </div>
          ) : null}
        </aside>
      </div>
      <ResearchTimeline workspace={workspace} completed={completed} />
    </div>
  );
}
