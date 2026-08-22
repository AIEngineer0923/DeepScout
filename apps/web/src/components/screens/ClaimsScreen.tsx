"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ExpandableText } from "@/components/ExpandableText";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { useT, useI18n } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { displayClaimStatement } from "@/presentation/demo";
import { presentTaskKey, presentWorkerIndex } from "@/presentation/fields";

export function ClaimsScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const params = useSearchParams();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(params.get("claim"));
  const filtered = useMemo(
    () => (workspace ? workspace.claims.filter((claim) => claim.statement.toLowerCase().includes(query.toLowerCase())) : []),
    [workspace, query],
  );
  if (!workspace) return <p className="empty">{t("claims.loading")}</p>;
  const claim = filtered.find((item) => item.id === selected) ?? filtered[0];
  const evidence = workspace.evidence.filter((item) => item.claim_id === claim?.id);
  const summary = [
    ["total", workspace.claims.length],
    ["supported", workspace.claims.filter((c) => ["supported", "verified"].includes(c.verification_status)).length],
    ["partial", workspace.claims.filter((c) => c.verification_status.includes("partial")).length],
    ["contradicted", workspace.contradictions.length],
    ["pending", workspace.claims.filter((c) => c.verification_status === "pending").length],
  ] as const;
  return (
    <div>
      <RunHeader workspace={workspace} />
      {demoReadOnly ? <p className="screen-intro">{t("demo.evidence.intro")}</p> : null}
      <div className="grid cols-metrics">
        {summary.map(([key, value]) => (
          <article key={key} className="card metric">
            <div className="k">{t(`claims.stat.${key}`)}</div>
            <div className="v">{value}</div>
          </article>
        ))}
      </div>
      <div className="claims-layout">
        <section className="card claims-list-card">
          <input className="input" placeholder={t("claims.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>{t("table.claim")}</th>
                  <th>{t("table.status")}</th>
                  <th>{t("table.sources")}</th>
                  <th>{t("table.task")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item, index) => (
                  <tr key={item.id} className={claim?.id === item.id ? "selected" : ""} onClick={() => setSelected(item.id)}>
                    <td className="wrap-text claims-statement">
                      <strong>C-{String(index + 1).padStart(2, "0")}</strong>{" "}
                      {displayClaimStatement(workspace, item.id, item.statement)}
                    </td>
                    <td>
                      <StatusBadge status={item.verification_status} />
                    </td>
                    <td>{item.independent_source_count}</td>
                    <td>{presentTaskKey(workspace, item.task_key)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <aside className="drawer claims-detail-drawer">
          {claim ? (
            <>
              <h2>{t("claims.selected")}</h2>
              <StatusBadge status={claim.verification_status} />
              <p className="wrap-text">{displayClaimStatement(workspace, claim.id, claim.statement)}</p>
              <p>
                {t("table.worker")}: {presentWorkerIndex(workspace, claim.worker_index, locale)}
              </p>
              <h3>{t("claims.evidence")}</h3>
              {evidence.map((item) => (
                <article key={item.id} style={{ marginBottom: 12 }}>
                  <ExpandableText text={`“${item.quote}”`} />
                  {item.snapshot_id ? (
                    <Link href={`/research/${workspace.run_id}/snapshots/${item.snapshot_id}`}>{t("claims.openSnapshot")}</Link>
                  ) : null}
                  {item.source_id ? (
                    <div>
                      <Link href={`/research/${workspace.run_id}/sources`}>{t("claims.openSource")}</Link>
                    </div>
                  ) : null}
                </article>
              ))}
              <Link href={`/research/${workspace.run_id}/quality`}>{t("claims.openQuality")} →</Link>
            </>
          ) : (
            <p className="empty">{t("claims.empty")}</p>
          )}
        </aside>
      </div>
    </div>
  );
}
