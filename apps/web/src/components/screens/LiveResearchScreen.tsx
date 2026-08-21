"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { formatCost, formatTokens, relativeTime } from "@/lib/format";
import { useI18n } from "@/i18n/context";
import { ExpandableText } from "@/components/ExpandableText";
import { MobileRunScreen } from "@/components/screens/MobileRunScreen";

export function LiveResearchScreen() {
  const { workspace, error } = useRun();
  const { t, locale } = useI18n();
  if (error) return <p className="badge bad">{error}</p>;
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  const running = workspace.workers.filter((w) => ["running", "claimed", "ready"].includes(w.state));
  return (
    <div>
      <RunHeader workspace={workspace} />
      <MobileRunScreen />
      <div className="grid cols-3 live-desktop">
        <section className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>{t("live.plan", { count: workspace.tasks.length })}</h2>
            <Link href={`/research/${workspace.run_id}/plan`}>{t("live.dagView")}</Link>
          </div>
          {workspace.tasks.map((task) => (
            <article key={task.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--ds-line)" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong className="wrap-text">{task.objective}</strong>
                <StatusBadge status={task.status} />
              </div>
              <div className="muted">{task.display_name}</div>
            </article>
          ))}
        </section>
        <section className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>{t("live.workers", { count: running.length })}</h2>
            <Link href={`/research/${workspace.run_id}/workers`}>{t("live.viewWorkers")}</Link>
          </div>
          {workspace.workers.map((worker) => (
            <article key={worker.worker_id} style={{ padding: "10px 0", borderBottom: "1px solid var(--ds-line)" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong className="wrap-text">{worker.display_name}</strong>
                <StatusBadge status={worker.state} />
              </div>
              <p className="wrap-text muted">{worker.assigned_task}</p>
            </article>
          ))}
        </section>
        <aside className="card">
          <h2>{t("live.overview")}</h2>
          <p>
            {t("provider.provider")}: {workspace.llm_provider}
          </p>
          <p>
            {t("provider.model")}: {workspace.llm_model}
          </p>
          <p>
            {t("provider.maxSources")}: {workspace.budget.max_sources}
          </p>
          <p>
            {t("provider.maxIterations")}: {workspace.budget.max_iterations}
          </p>
          <p>
            {t("nav.sources")}: {workspace.counts.sources}
          </p>
          <p>
            {t("nav.snapshot")}: {workspace.counts.snapshots}
          </p>
          <p>
            {t("table.claims")}: {workspace.counts.claims}
          </p>
          <p>
            {t("table.evidence")}: {workspace.counts.evidence}
          </p>
          <p>
            {t("nav.quality")}: {workspace.counts.contradictions}
          </p>
          <p>
            {t("provider.tokens")}: {formatTokens(workspace.usage.total_tokens, t("cost.unknown"))}
          </p>
          <p>
            {t("provider.appCost")}: {formatCost(workspace.usage.cost_usd, workspace.usage.cost_status, t("cost.unknown"))}
          </p>
          <p>
            {t("provider.evalCost")}:{" "}
            {formatCost(workspace.usage.evaluation_cost_usd, workspace.usage.evaluation_cost_usd == null ? "unknown" : "estimated", t("cost.unknown"))}
          </p>
        </aside>
      </div>
      <section className="card live-desktop" style={{ marginTop: 16 }}>
        <h2>{t("live.activity")}</h2>
        {workspace.activity.slice(-12).reverse().map((event) => (
          <div key={event.sequence} className="row" style={{ justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #f3f4f6" }}>
            <span className="wrap-text">{event.type}</span>
            <span className="muted">{relativeTime(event.created_at, locale)}</span>
          </div>
        ))}
        {workspace.activity.length === 0 ? <p className="empty">{t("live.waiting")}</p> : null}
      </section>
    </div>
  );
}
