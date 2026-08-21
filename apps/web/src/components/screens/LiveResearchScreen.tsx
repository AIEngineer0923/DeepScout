"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { formatCost, formatTokens, relativeTime } from "@/lib/format";
import { workerProgress } from "@/lib/visual";
import { useI18n } from "@/i18n/context";
import { MobileRunScreen } from "@/components/screens/MobileRunScreen";

export function LiveResearchScreen() {
  const { workspace, error } = useRun();
  const { t, locale } = useI18n();
  const [activityFilter, setActivityFilter] = useState("all");
  const activity = useMemo(() => {
    if (!workspace) return [];
    const rows = [...workspace.activity].reverse();
    if (activityFilter === "all") return rows.slice(0, 12);
    return rows.filter((event) => event.type.toLowerCase().includes(activityFilter)).slice(0, 12);
  }, [workspace, activityFilter]);
  if (error) return <p className="badge bad">{error}</p>;
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  const running = workspace.workers.filter((w) => ["running", "claimed", "ready"].includes(w.state));
  return (
    <div>
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
                <strong className="wrap-text">
                  <span className="task-index">{index + 1}.</span>
                  {task.objective}
                </strong>
                <div className="muted">{task.display_name}</div>
              </div>
              <StatusBadge status={task.status} />
            </article>
          ))}
        </section>
        <section className="card compact">
          <div className="card-head">
            <h2>{t("live.workers", { count: running.length })}</h2>
            <Link className="link-btn" href={`/research/${workspace.run_id}/workers`}>
              {t("live.viewWorkers")} →
            </Link>
          </div>
          {workspace.workers.map((worker) => {
            const pct = workerProgress(worker.state, worker.index);
            return (
              <article key={worker.worker_id} className="list-row" style={{ flexDirection: "column", alignItems: "stretch" }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong className="wrap-text">{worker.display_name}</strong>
                  <StatusBadge status={worker.state} />
                </div>
                <p className="wrap-text muted">{worker.assigned_task}</p>
                <div className="progress-label">
                  <span>{t("phase.running")}</span>
                  <span>{pct}%</span>
                </div>
                <div className="progress">
                  <span className={worker.state === "completed" ? "ok" : ""} style={{ width: `${pct}%` }} />
                </div>
              </article>
            );
          })}
        </section>
        <aside className="drawer">
          <h2>{t("live.overview")}</h2>
          <dl className="kv-list">
            <div className="kv-row">
              <dt>{t("new.step2")}</dt>
              <dd>{workspace.research_mode ?? "—"}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("provider.maxSources")}</dt>
              <dd>{workspace.budget.max_sources}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("provider.maxIterations")}</dt>
              <dd>{workspace.budget.max_iterations}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.outputLanguage")}</dt>
              <dd>{workspace.output_language ?? "—"}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("provider.provider")}</dt>
              <dd>{workspace.llm_provider}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("provider.model")}</dt>
              <dd>{workspace.llm_model}</dd>
            </div>
          </dl>
          <div className="panel-section">
            <h3>{t("live.progress")}</h3>
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
                <dt>{t("table.claims")}</dt>
                <dd>{workspace.counts.claims}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("table.evidence")}</dt>
                <dd>{workspace.counts.evidence}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("nav.quality")}</dt>
                <dd>{workspace.counts.contradictions}</dd>
              </div>
            </dl>
          </div>
          <div className="panel-section">
            <h3>{t("live.usage")}</h3>
            <dl className="kv-list">
              <div className="kv-row">
                <dt>{t("provider.tokens")}</dt>
                <dd>{formatTokens(workspace.usage.total_tokens, t("cost.unknown"))}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("provider.appCost")}</dt>
                <dd>{formatCost(workspace.usage.cost_usd, workspace.usage.cost_status, t("cost.unknown"))}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("provider.evalCost")}</dt>
                <dd>
                  {formatCost(
                    workspace.usage.evaluation_cost_usd,
                    workspace.usage.evaluation_cost_usd == null ? "unknown" : "estimated",
                    t("cost.unknown"),
                  )}
                </dd>
              </div>
            </dl>
          </div>
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
        </aside>
      </div>
      <section className="card live-desktop" style={{ marginTop: 18 }}>
        <div className="card-head">
          <h2>{t("live.activity")}</h2>
        </div>
        <div className="activity-tabs" role="group" aria-label={t("live.activity")}>
          {(["all", "phase", "worker", "tool"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={`activity-tab ${activityFilter === item ? "active" : ""}`}
              aria-pressed={activityFilter === item}
              onClick={() => setActivityFilter(item)}
            >
              {item === "all" ? t("activity.all") : t(`activity.${item}`)}
            </button>
          ))}
        </div>
        {activity.map((event) => (
          <div key={event.sequence} className="row" style={{ justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #f3f4f6" }}>
            <span className="wrap-text mono">{event.type}</span>
            <span className="muted">{relativeTime(event.created_at, locale)}</span>
          </div>
        ))}
        {activity.length === 0 ? <p className="empty">{t("live.waiting")}</p> : null}
      </section>
    </div>
  );
}
