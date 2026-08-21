"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

type Monitor = {
  id: string;
  name: string;
  goal: string;
  enabled: boolean;
  status: string;
  timezone: string;
  schedule_kind: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_change_at: string | null;
  last_run_id: string | null;
};

export function MonitorsScreen() {
  const t = useT();
  const [rows, setRows] = useState<Monitor[]>([]);
  const [name, setName] = useState("Daily monitor");
  const [goal, setGoal] = useState("");
  const [timezone, setTimezone] = useState("Europe/Rome");
  const [error, setError] = useState<string | null>(null);
  function reload() {
    api.listMonitors().then((data) => setRows(data as Monitor[])).catch(() => setRows([]));
  }
  useEffect(() => {
    reload();
  }, []);
  async function create() {
    setError(null);
    try {
      await api.createMonitor({
        name,
        goal,
        schedule_kind: "daily",
        timezone,
        hour: 9,
        minute: 0,
      });
      setGoal("");
      reload();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : t("monitors.failed"));
    }
  }
  return (
    <div>
      <h1 className="page-title">{t("monitors.title")}</h1>
      <p className="page-sub">{t("monitors.subtitle")}</p>
      <section className="card">
        <h2>{t("monitors.create")}</h2>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} aria-label={t("monitors.name")} />
        <textarea className="input" rows={3} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder={t("monitors.goal")} />
        <input className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)} aria-label={t("monitors.timezone")} />
        {error ? <p className="empty">{error}</p> : null}
        <button className="btn primary" data-testid="monitor-create" disabled={!goal.trim()} onClick={() => void create()}>
          {t("monitors.save")}
        </button>
      </section>
      <div className="table-wrap card">
        <table className="data">
          <thead>
            <tr>
              <th>{t("monitors.name")}</th>
              <th>{t("table.status")}</th>
              <th>{t("monitors.next")}</th>
              <th>{t("monitors.last")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={`/monitors/${row.id}`}>{row.name}</Link>
                  <div className="muted wrap-text">{row.goal}</div>
                </td>
                <td>{row.status}</td>
                <td>{row.next_run_at ?? "—"}</td>
                <td>
                  {row.last_run_id ? <Link href={`/research/${row.last_run_id}`}>{t("monitors.openRun")}</Link> : "—"}
                </td>
                <td className="row">
                  <button className="btn" type="button" onClick={() => void api.patchMonitor(row.id, { enabled: !row.enabled }).then(reload)}>
                    {row.enabled ? t("monitors.pause") : t("monitors.enable")}
                  </button>
                  <button className="btn" data-testid="monitor-run-now" type="button" onClick={() => void api.runMonitorNow(row.id).then((created) => (window.location.href = `/research/${created.run_id}`))}>
                    {t("monitors.runNow")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
