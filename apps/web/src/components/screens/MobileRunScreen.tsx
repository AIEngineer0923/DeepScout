"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { PhaseStepper } from "@/components/run/PhaseStepper";
import { api } from "@/lib/api";
import { formatCost, formatTokens } from "@/lib/format";
import { workerProgress } from "@/lib/visual";
import { useT } from "@/i18n/context";
import { ExpandableText } from "@/components/ExpandableText";

export function MobileRunScreen() {
  const { workspace, reload } = useRun();
  const t = useT();
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  const worker = workspace.workers.find((item) => item.state === "running") ?? workspace.workers[0];
  const running = ["running", "pending"].includes(workspace.status);
  const pct = worker ? workerProgress(worker.state, worker.index) : 0;

  return (
    <div className="grid live-mobile">
      <section className="card compact mobile-run-head">
        <StatusBadge status={workspace.status} />
        <h2 className="wrap-text" style={{ margin: "8px 0 0", fontSize: 18 }}>
          {workspace.goal}
        </h2>
        <PhaseStepper completed={workspace.completed_phases} status={workspace.status} />
      </section>
      {worker ? (
        <section className="card compact">
          <h2>{t("mobile.activeWorker")}</h2>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong className="wrap-text">{worker.display_name}</strong>
            <StatusBadge status={worker.state} />
          </div>
          <p className="wrap-text muted">{worker.assigned_task}</p>
          <div className="progress-label">
            <span>{t("phase.running")}</span>
            <span>{pct}%</span>
          </div>
          <div className="progress lg">
            <span style={{ width: `${pct}%` }} />
          </div>
        </section>
      ) : null}
      <section className="card compact">
        <h2>{t("mobile.progress")}</h2>
        <div className="mobile-stat-grid">
          <div className="mobile-stat">
            <div className="k">{t("nav.sources")}</div>
            <div className="v">{workspace.counts.sources}</div>
          </div>
          <div className="mobile-stat">
            <div className="k">{t("table.evidence")}</div>
            <div className="v">{workspace.counts.evidence}</div>
          </div>
          <div className="mobile-stat">
            <div className="k">{t("table.claims")}</div>
            <div className="v">{workspace.counts.claims}</div>
          </div>
          <div className="mobile-stat">
            <div className="k">{t("provider.maxSources")}</div>
            <div className="v">{workspace.budget.max_sources}</div>
          </div>
        </div>
        <dl className="kv-list" style={{ marginTop: 12 }}>
          <div className="kv-row">
            <dt>{t("provider.tokens")}</dt>
            <dd>{formatTokens(workspace.usage.total_tokens, t("cost.unknown"))}</dd>
          </div>
          <div className="kv-row">
            <dt>{t("provider.appCost")}</dt>
            <dd>{formatCost(workspace.usage.cost_usd, workspace.usage.cost_status, t("cost.unknown"))}</dd>
          </div>
        </dl>
      </section>
      <section className="card compact">
        <h2>{t("mobile.latestEvidence")}</h2>
        {workspace.evidence.slice(-3).reverse().map((item) => (
          <ExpandableText key={item.id} text={`“${item.quote}”`} />
        ))}
        {workspace.evidence.length === 0 ? <p className="empty">{t("claims.empty")}</p> : null}
      </section>
      <div className="form-actions">
        {running ? (
          <button className="btn danger" onClick={() => void api.cancel(workspace.run_id).then(reload)}>
            {t("action.cancelResearch")}
          </button>
        ) : null}
        <Link className="btn primary" href={`/research/${workspace.run_id}/report`}>
          {t("nav.report")}
        </Link>
        <Link className="btn" href={`/research/${workspace.run_id}/sources`}>
          {t("nav.sources")}
        </Link>
      </div>
    </div>
  );
}
