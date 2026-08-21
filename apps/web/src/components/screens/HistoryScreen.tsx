"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatCost, formatTokens, relativeTime } from "@/lib/format";
import type { RunListItem } from "@/lib/types";
import { StatusBadge } from "../StatusBadge";
import { Tabs } from "../Tabs";
import { useI18n } from "@/i18n/context";

export function HistoryScreen() {
  const { t, locale } = useI18n();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const limit = 8;

  useEffect(() => {
    api
      .listRuns({ status: status || undefined, q: q || undefined, limit, offset })
      .then((data) => {
        setRows(data.items);
        setTotal(data.total);
      })
      .catch(() => undefined);
  }, [status, q, offset]);

  return (
    <div>
      <h1 className="page-title">{t("history.title")}</h1>
      <p className="page-sub">{t("history.subtitle")}</p>
      <Tabs
        items={[
          { id: "", label: t("history.all") },
          { id: "completed", label: t("status.completed") },
          { id: "failed", label: t("status.failed") },
          { id: "cancelled", label: t("status.cancelled") },
        ]}
        value={status}
        onChange={(id) => {
          setStatus(id);
          setOffset(0);
        }}
        ariaLabel={t("history.title")}
      />
      <div className="toolbar">
        <input
          className="input grow"
          placeholder={t("history.search")}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
        <a className="btn" href={api.historyCsvUrl({ status: status || undefined, q: q || undefined })}>
          {t("action.exportHistory")}
        </a>
      </div>
      <section className="card">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t("table.research")}</th>
                <th>{t("table.status")}</th>
                <th>{t("table.stages")}</th>
                <th>{t("table.duration")}</th>
                <th>{t("table.tokens")}</th>
                <th>{t("table.cost")}</th>
                <th>{t("table.updated")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.id}>
                  <td className="wrap-text">
                    <Link href={`/research/${run.id}`}>{run.goal}</Link>
                    <div className="mono muted">{run.id}</div>
                  </td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>
                    {run.completed_task_count}/{run.task_count}
                  </td>
                  <td>{relativeTime(run.started_at, locale)}</td>
                  <td>{formatTokens(run.total_tokens, t("cost.unknown"))}</td>
                  <td>{formatCost(run.cost_usd, run.cost_status, t("cost.unknown"))}</td>
                  <td>{relativeTime(run.updated_at, locale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row" style={{ justifyContent: "space-between", marginTop: 12 }}>
          <span className="muted">{t("history.showing", { shown: rows.length, total })}</span>
          <div className="row">
            <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              {t("action.previous")}
            </button>
            <button className="btn" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
              {t("action.next")}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
