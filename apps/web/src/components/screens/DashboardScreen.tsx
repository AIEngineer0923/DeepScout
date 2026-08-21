"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { rememberRunId } from "@/lib/current-run";
import { elapsed, formatCost, formatTokens, relativeTime } from "@/lib/format";
import type { Overview } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { PhaseStepper } from "@/components/run/PhaseStepper";
import { useI18n } from "@/i18n/context";

const EMPTY: Overview = {
  active: null,
  recent: [],
  totals: {
    runs: 0,
    sources: 0,
    evidence: 0,
    claims: 0,
    known_cost_usd: null,
    cost_status: "unknown",
    avg_completion_seconds: null,
  },
  identity: { label: "Local workspace", role: "Operator" },
  langsmith: { connected: false, project: "deepscout-dev", region: "EU", tracing: false },
  providers: {},
};

export function DashboardScreen() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const [overview, setOverview] = useState<Overview>(EMPTY);
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState<"quick" | "standard" | "deep">("standard");
  const [outputLanguage, setOutputLanguage] = useState("en");
  const [busy, setBusy] = useState(false);
  const active = overview.active;

  useEffect(() => {
    api.overview().then(setOverview).catch(() => setOverview(EMPTY));
  }, []);

  async function start() {
    if (!goal.trim()) return;
    setBusy(true);
    try {
      const created = await api.createRun({
        goal: goal.trim(),
        research_mode: mode,
        output_language: outputLanguage,
      });
      rememberRunId(created.id);
      await api.execute(created.id);
      router.push(`/research/${created.id}`);
    } finally {
      setBusy(false);
    }
  }

  const metrics = useMemo(
    () => [
      { k: t("dashboard.metric.runs"), v: String(overview.totals.runs) },
      { k: t("dashboard.metric.sources"), v: String(overview.totals.sources) },
      { k: t("dashboard.metric.evidence"), v: String(overview.totals.evidence) },
      { k: t("dashboard.metric.claims"), v: String(overview.totals.claims) },
      {
        k: t("dashboard.metric.avg"),
        v: overview.totals.avg_completion_seconds ? `${Math.round(overview.totals.avg_completion_seconds / 60)}m` : "—",
      },
      { k: t("dashboard.metric.cost"), v: formatCost(overview.totals.known_cost_usd, overview.totals.cost_status, t("cost.unknown")) },
    ],
    [overview, t],
  );

  return (
    <div className="grid" style={{ gap: 20 }}>
      <div>
        <h1 className="page-title">{t("dashboard.title")}</h1>
        <p className="page-sub">{t("dashboard.subtitle")}</p>
      </div>
      <div className="grid cols-2">
        <section className="card">
          <label htmlFor="quick-goal">{t("dashboard.goalLabel")}</label>
          <textarea
            id="quick-goal"
            className="textarea"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder={t("dashboard.goalPlaceholder")}
          />
          <div className="chip-row" style={{ marginTop: 12 }}>
            {(["quick", "standard", "deep"] as const).map((item) => (
              <button
                key={item}
                type="button"
                className={`chip ${mode === item ? "selected" : ""}`}
                data-testid={`dash-mode-${item}`}
                onClick={() => setMode(item)}
              >
                {t(`new.mode.${item}`)}
              </button>
            ))}
            <span className="chip">{t("dashboard.automaticModels")}</span>
            <select
              className="select"
              style={{ maxWidth: 160 }}
              value={outputLanguage}
              onChange={(e) => setOutputLanguage(e.target.value)}
              aria-label={t("new.outputLanguage")}
            >
              <option value="en">{t("lang.en")}</option>
              <option value="it">{t("lang.it")}</option>
            </select>
          </div>
          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button className="btn primary" disabled={busy || !goal.trim()} onClick={() => void start()}>
              {t("action.start")} →
            </button>
          </div>
        </section>
        <section className="card">
          <h2>{t("dashboard.active")}</h2>
          {active ? (
            <>
              <p className="wrap-text">
                <strong>{active.goal}</strong>
              </p>
              <StatusBadge status={active.status} />
              <p className="muted">
                {t("phase.running")} {elapsed(active.started_at ?? active.created_at)}
              </p>
              <PhaseStepper completed={[]} status={active.status} />
              <p className="muted">
                {active.task_count} {t("nav.workers").toLowerCase()} · {active.source_count} {t("nav.sources").toLowerCase()} ·{" "}
                {active.evidence_count} {t("nav.claims").toLowerCase()}
              </p>
              <Link className="btn" href={`/research/${active.id}`}>
                {t("action.openResearch")} →
              </Link>
            </>
          ) : (
            <p className="empty">{t("dashboard.noActive")}</p>
          )}
        </section>
      </div>
      <div className="grid cols-metrics">
        {metrics.map((metric) => (
          <article key={metric.k} className="card metric">
            <div className="k">{metric.k}</div>
            <div className="v">{metric.v}</div>
          </article>
        ))}
      </div>
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>{t("dashboard.recent")}</h2>
          <Link href="/history">{t("action.viewHistory")}</Link>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t("table.research")}</th>
                <th>{t("table.status")}</th>
                <th>{t("table.sources")}</th>
                <th>{t("table.evidence")}</th>
                <th>{t("table.tokens")}</th>
                <th>{t("table.updated")}</th>
              </tr>
            </thead>
            <tbody>
              {overview.recent.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty">
                    {t("empty.runs")}
                  </td>
                </tr>
              ) : (
                overview.recent.map((run) => (
                  <tr key={run.id} onClick={() => router.push(`/research/${run.id}`)} style={{ cursor: "pointer" }}>
                    <td>
                      <Link href={`/research/${run.id}`} className="wrap-text">
                        {run.goal}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge status={run.status} />
                    </td>
                    <td>{run.source_count}</td>
                    <td>{run.evidence_count}</td>
                    <td>{formatTokens(run.total_tokens, t("cost.unknown"))}</td>
                    <td>{relativeTime(run.updated_at, locale)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
