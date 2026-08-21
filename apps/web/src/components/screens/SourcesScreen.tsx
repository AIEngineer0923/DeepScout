"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { ExternalLink } from "@/components/ExternalLink";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function SourcesScreen() {
  const { workspace } = useRun();
  const t = useT();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [prefError, setPrefError] = useState<string | null>(null);
  const filtered = useMemo(() => {
    if (!workspace) return [];
    return workspace.sources.filter((source) => {
      const hay = `${source.title} ${source.domain} ${source.url}`.toLowerCase();
      const matchesQuery = hay.includes(query.toLowerCase());
      const matchesStatus = status === "all" || source.fetch_state === status;
      return matchesQuery && matchesStatus;
    });
  }, [workspace, query, status]);
  if (!workspace) return <p className="empty">{t("sources.loading")}</p>;
  const current = workspace;
  async function setPreference(action: "pin" | "exclude") {
    if (!source) return;
    setPrefError(null);
    try {
      await api.setSourcePreference(current.run_id, {
        action,
        identity_kind: "url",
        identity_value: source.url,
      });
      window.location.reload();
    } catch (exc) {
      setPrefError(exc instanceof Error ? exc.message : t("sources.prefFailed"));
    }
  }
  async function undoPreference() {
    const match = current.source_preferences?.find((item) => item.identity_value === source?.url);
    if (!match) return;
    await api.deleteSourcePreference(current.run_id, match.id);
    window.location.reload();
  }
  const source = filtered.find((item) => item.id === selected) ?? filtered[0];
  const stats = {
    discovered: workspace.sources.length,
    fetched: workspace.sources.filter((s) => s.fetch_state === "fetched").length,
    snapshots: workspace.counts.snapshots,
    claims: workspace.counts.claims,
    evidence: workspace.counts.evidence,
  };
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>{t("sources.title")}</h2>
          <p className="muted">{t("sources.subtitle")}</p>
        </div>
        <a className="btn" href={api.exportUrl(workspace.run_id, "sources-csv")}>{t("action.exportSources")} CSV</a>
        <a className="btn" href={api.exportUrl(workspace.run_id, "json")}>{t("action.exportSources")} JSON</a>
      </div>
      <div className="grid cols-metrics" style={{ margin: "12px 0" }}>
        {(
          [
            ["discovered", stats.discovered],
            ["fetched", stats.fetched],
            ["snapshots", stats.snapshots],
            ["claims", stats.claims],
            ["evidence", stats.evidence],
          ] as const
        ).map(([key, value]) => (
          <article key={key} className="card metric">
            <div className="k">{t(`sources.stat.${key}`)}</div>
            <div className="v">{value}</div>
          </article>
        ))}
      </div>
      <div className="grid cols-2">
        <section className="card">
          <div className="toolbar">
            <input className="input grow" placeholder={t("sources.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
            <select className="select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t("table.status")}>
              <option value="all">{t("sources.allStatus")}</option>
              <option value="fetched">{t("status.fetched")}</option>
              <option value="discovered">{t("status.discovered")}</option>
            </select>
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>{t("table.source")}</th><th>{t("table.status")}</th><th>{t("sources.pref")}</th><th>{t("table.worker")}</th><th>{t("table.claims")}</th><th>{t("table.evidence")}</th></tr></thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className={source?.id === item.id ? "selected" : ""} onClick={() => setSelected(item.id)}>
                    <td>
                      <div className="wrap-text"><strong>{item.title}</strong></div>
                      <div className="muted">{item.domain}</div>
                    </td>
                    <td><StatusBadge status={item.fetch_state} /></td>
                    <td>{item.preference ?? "normal"}</td>
                    <td>{item.worker_index ? `W${String(item.worker_index).padStart(2, "0")}` : "—"}</td>
                    <td>{item.claim_count}</td>
                    <td>{item.evidence_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <aside className="drawer">
          {source ? (
            <>
              <h2 className="wrap-text">{source.title}</h2>
              <StatusBadge status={source.fetch_state} />
              <p><ExternalLink href={source.url}><span className="wrap-text">{source.url}</span></ExternalLink></p>
              <p>
                {t("sources.type")}: {source.source_type}
              </p>
              <p>{t("nav.snapshot")}: {source.snapshot_available ? t("sources.snapshotAvailable") : t("sources.snapshotMissing")}</p>
              <p>{t("sources.pref")}: {source.preference ?? "normal"}</p>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button className="btn" data-testid="pin-source" type="button" onClick={() => void setPreference("pin")}>{t("sources.pin")}</button>
                <button className="btn" data-testid="exclude-source" type="button" onClick={() => void setPreference("exclude")}>{t("sources.exclude")}</button>
                <button className="btn" data-testid="undo-source-pref" type="button" onClick={() => void undoPreference()}>{t("sources.undo")}</button>
              </div>
              {prefError ? <p className="empty">{prefError}</p> : null}
              {source.task_id ? <p>{t("table.task")}: {source.task_key}</p> : null}
              {source.worker_index ? <Link href={`/research/${workspace.run_id}/workers`}>{t("action.open")} W{String(source.worker_index).padStart(2, "0")}</Link> : null}
              {source.snapshot_id ? (
                <Link className="btn" href={`/research/${workspace.run_id}/snapshots/${source.snapshot_id}`}>{t("sources.viewSnapshot")}</Link>
              ) : null}
              <Link href={`/research/${workspace.run_id}/claims`}>{t("sources.openClaims")} →</Link>
            </>
          ) : <p className="empty">{t("sources.empty")}</p>}
        </aside>
      </div>
    </div>
  );
}
