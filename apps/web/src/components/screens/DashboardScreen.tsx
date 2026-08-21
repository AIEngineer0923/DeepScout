"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { rememberRunId } from "@/lib/current-run";
import { elapsed, formatCost, formatTokens, relativeTime } from "@/lib/format";
import type { Overview } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
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

const PHASES = ["plan", "research", "verify", "synthesis", "report"] as const;

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
    () =>
      [
        { k: t("dashboard.metric.runs"), v: String(overview.totals.runs), sub: t("dashboard.metric.allTime"), tone: "blue" },
        { k: t("dashboard.metric.sources"), v: String(overview.totals.sources), sub: t("dashboard.metric.across"), tone: "green" },
        { k: t("dashboard.metric.evidence"), v: String(overview.totals.evidence), sub: t("dashboard.metric.across"), tone: "purple" },
        { k: t("dashboard.metric.claims"), v: String(overview.totals.claims), sub: t("dashboard.metric.across"), tone: "teal" },
        {
          k: t("dashboard.metric.avg"),
          v: overview.totals.avg_completion_seconds ? `${Math.round(overview.totals.avg_completion_seconds / 60)}m` : "—",
          sub: t("dashboard.metric.completedRuns"),
          tone: "orange",
        },
        {
          k: t("dashboard.metric.cost"),
          v: formatCost(overview.totals.known_cost_usd, overview.totals.cost_status, t("cost.unknown")),
          sub: t("dashboard.metric.knownSpend"),
          tone: "blue",
        },
      ] as const,
    [overview, t],
  );

  const activePhaseIndex = active?.status === "completed" ? 4 : active?.status === "running" ? 1 : 0;

  return (
    <div className="grid" style={{ gap: 22 }}>
      <div className="page-head">
        <h1 className="page-title">
          {t("dashboard.title")}, {overview.identity.label}
        </h1>
        <p className="page-sub">{t("dashboard.subtitle")}</p>
      </div>
      {overview.identity.role === "Anonymous" ? (
        <section className="card" style={{ display: "grid", gap: 12 }}>
          <p className="page-sub" style={{ margin: 0 }}>
            Explore completed research without an account. Sign in only if you want to run your own
            research with your own provider credentials.
          </p>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            <Link className="btn primary" href="/demo">
              Explore Demo
            </Link>
            <Link className="btn" href="/login">
              Sign in
            </Link>
            <a className="btn" href="https://github.com/francescoveryra-dot/deepscout">
              View on GitHub
            </a>
            <a className="btn" href="https://github.com/francescoveryra-dot/deepscout#quick-start">
              Run Locally
            </a>
            <a className="btn" href="https://github.com/francescoveryra-dot/deepscout/blob/main/docs/DEPLOYMENT.md">
              Deploy Your Own
            </a>
            <a className="btn" href="https://github.com/francescoveryra-dot/deepscout/blob/main/ARCHITECTURE.md">
              Architecture
            </a>
          </div>
        </section>
      ) : null}
      <div className="grid cols-2">
        <section className="card">
          <h2>{t("dashboard.goalLabel")}</h2>
          <textarea
            id="quick-goal"
            className="textarea"
            style={{ minHeight: 132 }}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder={t("dashboard.goalPlaceholder")}
          />
          <div className="chip-row" style={{ marginTop: 14 }}>
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
          <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
            <button className="btn primary" disabled={busy || !goal.trim()} onClick={() => void start()}>
              {t("action.start")} →
            </button>
          </div>
        </section>
        <section className="card">
          <p className="card-eyebrow">{t("dashboard.active")}</p>
          {active ? (
            <>
              <p className="wrap-text" style={{ margin: "0 0 10px" }}>
                <strong>{active.goal}</strong>
              </p>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
                <StatusBadge status={active.status} />
                <span className="muted">{elapsed(active.started_at ?? active.created_at)}</span>
              </div>
              <div className="progress-label">
                <span>{t("phase.running")}</span>
                <span>{Math.min(100, Math.round(((active.completed_task_count ?? 0) / Math.max(active.task_count ?? 1, 1)) * 100))}%</span>
              </div>
              <div className="progress lg" aria-hidden="true">
                <span
                  style={{
                    width: `${Math.min(100, Math.round(((active.completed_task_count ?? 0) / Math.max(active.task_count ?? 1, 1)) * 100))}%`,
                  }}
                />
              </div>
              <ol className="phase-list">
                {PHASES.map((phase, index) => {
                  const done = index < activePhaseIndex;
                  const runningPhase = index === activePhaseIndex && active.status !== "completed";
                  return (
                    <li key={phase}>
                      <span className={`dot-step ${done ? "done" : ""} ${runningPhase ? "active" : ""}`}>{done ? "✓" : ""}</span>
                      <span>
                        <strong>{t(`phase.${phase}`)}</strong>
                        <div className="muted">{done ? t("phase.completed") : runningPhase ? t("phase.running") : t("phase.pending")}</div>
                      </span>
                      <span className="muted mono">{runningPhase || done ? elapsed(active.started_at ?? active.created_at) : "—"}</span>
                    </li>
                  );
                })}
              </ol>
              <p className="muted" style={{ margin: "12px 0" }}>
                {active.task_count} {t("nav.workers").toLowerCase()} · {active.source_count} {t("nav.sources").toLowerCase()} · {active.evidence_count}{" "}
                {t("table.evidence").toLowerCase()}
              </p>
              <Link className="btn" style={{ width: "100%" }} href={`/research/${active.id}`}>
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
            <span className={`metric-icon ${metric.tone}`} aria-hidden="true">
              ●
            </span>
            <div className="k">{metric.k}</div>
            <div className="v">{metric.v}</div>
            <div className="sub">{metric.sub}</div>
          </article>
        ))}
      </div>
      <section className="card">
        <div className="card-head">
          <h2>{t("dashboard.recent")}</h2>
          <Link className="link-btn" href="/history">
            {t("action.viewHistory")} →
          </Link>
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
                        <strong>{run.goal}</strong>
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
