"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatCost, formatTokens } from "@/lib/format";
import { useT } from "@/i18n/context";
import { ExpandableText } from "@/components/ExpandableText";

export function MobileRunScreen() {
  const { workspace, reload } = useRun();
  const t = useT();
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  const worker = workspace.workers.find((item) => item.state === "running") ?? workspace.workers[0];
  const running = ["running", "pending"].includes(workspace.status);
  return (
    <div className="grid live-mobile">
      {worker ? (
        <section className="card">
          <h2>{t("mobile.activeWorker")}</h2>
          <p className="wrap-text">
            <strong>{worker.display_name}</strong>
          </p>
          <StatusBadge status={worker.state} />
          <p className="wrap-text muted">{worker.assigned_task}</p>
        </section>
      ) : null}
      <section className="card">
        <h2>{t("mobile.progress")}</h2>
        <p>
          {t("nav.sources")} {workspace.counts.sources} · {t("table.evidence")} {workspace.counts.evidence} ·{" "}
          {t("table.claims")} {workspace.counts.claims}
        </p>
        <p>
          {t("provider.maxSources")}: {workspace.budget.max_sources}
        </p>
        <p>
          {t("provider.tokens")} {formatTokens(workspace.usage.total_tokens, t("cost.unknown"))} · {t("provider.appCost")}{" "}
          {formatCost(workspace.usage.cost_usd, workspace.usage.cost_status, t("cost.unknown"))}
        </p>
      </section>
      <section className="card">
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
        <Link className="btn" href={`/research/${workspace.run_id}/report`}>
          {t("nav.report")}
        </Link>
        <Link className="btn" href={`/research/${workspace.run_id}/sources`}>
          {t("nav.sources")}
        </Link>
      </div>
    </div>
  );
}
