"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { useI18n, useT } from "@/i18n/context";
import {
  formatLearningTimestamp,
  presentAuditEventType,
  presentCandidateStatus,
  presentCandidateType,
  presentFailureClass,
  presentLearningSubsystem,
  presentPromotionVerdict,
  presentReviewState,
  presentRiskLevel,
  presentLearningHealth,
  presentPolicyVerdict,
  presentAttribution,
  formatDelta,
  riskForCandidateType,
} from "@/presentation/learning";

type LearningCase = {
  id: string;
  case_key: string;
  subsystem: string;
  failure_class: string;
  symptom: string;
  review_state: string;
  trust_level: string;
  root_cause_class: string | null;
  created_at: string;
};

type LearningCandidate = {
  id: string;
  candidate_key: string;
  title: string;
  status: string;
  candidate_type: string;
  promotion_verdict: string | null;
  created_at: string;
};

type LearningPolicy = {
  id: string;
  policy_key: string;
  policy_family: string | null;
  version_label: string;
  active: boolean;
  promotion_reason: string | null;
  created_at: string;
};

type LearningAuditEvent = {
  id: string;
  event_type: string;
  policy_key: string | null;
  policy_family: string | null;
  previous_version_label: string | null;
  new_version_label: string | null;
  reason: string | null;
  actor_label: string;
  created_at: string;
};

type LearningMetrics = {
  cases_total: number;
  cases_open: number;
  cases_diagnosed: number;
  candidates_proposed: number;
  candidates_evaluated: number;
  candidates_promoted: number;
  candidates_rejected: number;
  candidates_requires_review: number;
  active_policy_versions: number;
};

type LearningEffectiveness = {
  health: string;
  health_reason: string;
  production_counts: Record<string, number>;
  policy_win_rate: number | null;
  rollback_rate: number | null;
  experience_sample_count: number;
  opportunity_cases: number;
  user_feedback_cases: number;
  hitl_learning_cases: number;
  policy_drift_flags: string[];
  debt: {
    unresolved_cases: number;
    unevaluated_candidates: number;
    stale_experiments: number;
    pending_hitl_reviews: number;
    incomplete_monitoring: number;
    policies_insufficient_evidence: number;
  } | null;
  families: Array<{
    policy_family: string;
    policy_key: string;
    version_label: string;
    verdict: string;
    attribution: string;
    quality_delta: number | null;
    cost_delta: number | null;
    failure_recurrence_rate: number | null;
    monitoring_samples: number;
    rolled_back: boolean;
    before: { sample_count: number; quality_mean: number | null; cost_mean: number | null };
    after: { sample_count: number; quality_mean: number | null; cost_mean: number | null };
  }>;
};

const EMPTY_METRICS: LearningMetrics = {
  cases_total: 0,
  cases_open: 0,
  cases_diagnosed: 0,
  candidates_proposed: 0,
  candidates_evaluated: 0,
  candidates_promoted: 0,
  candidates_rejected: 0,
  candidates_requires_review: 0,
  active_policy_versions: 0,
};

function canReviewCandidate(candidate: LearningCandidate): boolean {
  return (
    candidate.status === "requires_human_review" || candidate.promotion_verdict === "requires_human_review"
  );
}

export function LearningScreen() {
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const [cases, setCases] = useState<LearningCase[]>([]);
  const [candidates, setCandidates] = useState<LearningCandidate[]>([]);
  const [policies, setPolicies] = useState<LearningPolicy[]>([]);
  const [audit, setAudit] = useState<LearningAuditEvent[]>([]);
  const [metrics, setMetrics] = useState<LearningMetrics>(EMPTY_METRICS);
  const [effectiveness, setEffectiveness] = useState<LearningEffectiveness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);

  const load = useCallback(() => {
    setError(null);
    Promise.all([
      api.listLearningCases(),
      api.listLearningCandidates(),
      api.getLearningMetrics(),
      api.getLearningEffectiveness(),
      api.listLearningPolicies(),
      api.listLearningAudit(),
    ])
      .then(([caseRows, candidateRows, metricRows, effectivenessRows, policyRows, auditRows]) => {
        setCases(caseRows);
        setCandidates(candidateRows);
        setMetrics(metricRows);
        setEffectiveness(effectivenessRows);
        setPolicies(policyRows);
        setAudit(auditRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const activePolicies = useMemo(() => policies.filter((policy) => policy.active), [policies]);

  const metricCards = useMemo(
    () => [
      { key: "casesTotal", value: metrics.cases_total },
      { key: "casesOpen", value: metrics.cases_open },
      { key: "casesDiagnosed", value: metrics.cases_diagnosed },
      { key: "candidatesProposed", value: metrics.candidates_proposed },
      { key: "candidatesEvaluated", value: metrics.candidates_evaluated },
      { key: "candidatesRequiresReview", value: metrics.candidates_requires_review },
      { key: "candidatesPromoted", value: metrics.candidates_promoted },
      { key: "candidatesRejected", value: metrics.candidates_rejected },
      { key: "activePolicies", value: metrics.active_policy_versions },
    ],
    [metrics],
  );

  async function approveCandidate(candidate: LearningCandidate) {
    setBusy(candidate.id);
    setError(null);
    try {
      await api.approveLearningCandidate(candidate.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("learning.actions.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function rejectCandidate(candidate: LearningCandidate) {
    setBusy(candidate.id);
    setError(null);
    try {
      await api.rejectLearningCandidate(candidate.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("learning.actions.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function rollbackPolicy(policy: LearningPolicy) {
    setBusy(policy.id);
    setError(null);
    try {
      await api.rollbackLearningPolicy(policy.policy_key);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("learning.actions.failed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <h1 className="page-title">{t("learning.title")}</h1>
      <p className="page-sub">{t("learning.subtitle")}</p>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {effectiveness ? (
        <section className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <h2>{t("learning.effectiveness.title")}</h2>
            <span className="badge run">{presentLearningHealth(effectiveness.health, locale)}</span>
          </div>
          <p className="muted wrap-text">{effectiveness.health_reason}</p>
          <div className="grid cols-metrics-4" style={{ marginTop: 12 }}>
            <article className="card metric">
              <div className="k">{t("learning.effectiveness.experienceSamples")}</div>
              <div className="v">{effectiveness.experience_sample_count}</div>
            </article>
            <article className="card metric">
              <div className="k">{t("learning.effectiveness.terminalRuns")}</div>
              <div className="v">{effectiveness.production_counts.terminal_runs ?? 0}</div>
            </article>
            <article className="card metric">
              <div className="k">{t("learning.effectiveness.winRate")}</div>
              <div className="v">
                {effectiveness.policy_win_rate != null
                  ? `${Math.round(effectiveness.policy_win_rate * 100)}%`
                  : "—"}
              </div>
            </article>
            <article className="card metric">
              <div className="k">{t("learning.effectiveness.rollbackRate")}</div>
              <div className="v">
                {effectiveness.rollback_rate != null
                  ? `${Math.round(effectiveness.rollback_rate * 100)}%`
                  : "—"}
              </div>
            </article>
          </div>
          {effectiveness.debt ? (
            <dl className="kv-list compact" style={{ marginTop: 12 }}>
              <div className="kv-row">
                <dt>{t("learning.effectiveness.debt.unresolved")}</dt>
                <dd>{effectiveness.debt.unresolved_cases}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("learning.effectiveness.debt.unevaluated")}</dt>
                <dd>{effectiveness.debt.unevaluated_candidates}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("learning.effectiveness.debt.monitoring")}</dt>
                <dd>{effectiveness.debt.incomplete_monitoring}</dd>
              </div>
              <div className="kv-row">
                <dt>{t("learning.effectiveness.debt.insufficientEvidence")}</dt>
                <dd>{effectiveness.debt.policies_insufficient_evidence}</dd>
              </div>
            </dl>
          ) : null}
          {effectiveness.families.length > 0 ? (
            <div className="stack" style={{ gap: 12, marginTop: 16 }}>
              {effectiveness.families.map((family) => (
                <article key={`${family.policy_key}-${family.version_label}`} className="card" style={{ padding: 12 }}>
                  <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>
                      {family.policy_family} · {family.version_label}
                    </strong>
                    <span className="badge">{presentPolicyVerdict(family.verdict, locale)}</span>
                  </div>
                  <p className="muted">{family.policy_key}</p>
                  <dl className="kv-list compact">
                    <div className="kv-row">
                      <dt>{t("learning.effectiveness.beforeAfter")}</dt>
                      <dd>
                        {family.before.sample_count} → {family.after.sample_count}{" "}
                        {t("learning.effectiveness.samples")}
                      </dd>
                    </div>
                    <div className="kv-row">
                      <dt>{t("learning.effectiveness.qualityDelta")}</dt>
                      <dd>{formatDelta(family.quality_delta, locale)}</dd>
                    </div>
                    <div className="kv-row">
                      <dt>{t("learning.effectiveness.costDelta")}</dt>
                      <dd>{formatDelta(family.cost_delta, locale)}</dd>
                    </div>
                    <div className="kv-row">
                      <dt>{t("learning.effectiveness.evidence")}</dt>
                      <dd>{presentAttribution(family.attribution, locale)}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          ) : (
            <p className="empty" style={{ marginTop: 12 }}>
              {t("learning.effectiveness.noPolicies")}
            </p>
          )}
        </section>
      ) : null}

      <section aria-labelledby="learning-metrics-heading">
        <h2 id="learning-metrics-heading" className="sr-only">
          {t("learning.metrics.title")}
        </h2>
        <div className="grid cols-metrics-7" style={{ marginTop: 16 }}>
          {metricCards.map((metric) => (
            <article key={metric.key} className="card metric">
              <div className="k">{t(`learning.metrics.${metric.key}`)}</div>
              <div className="v">{metric.value}</div>
            </article>
          ))}
        </div>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>{t("learning.cases.title")}</h2>
        {cases.length === 0 ? <p className="empty">{t("learning.cases.empty")}</p> : null}
        <div className="stack" style={{ gap: 12, marginTop: 12 }}>
          {cases.map((item) => (
            <article key={item.id} className="card" style={{ padding: 12 }}>
              <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <strong>{presentLearningSubsystem(item.subsystem, locale)}</strong>
                <span className="muted">{presentReviewState(item.review_state, locale)}</span>
              </div>
              <p className="wrap-text">{item.symptom}</p>
              <p className="muted">
                {t("learning.cases.failure")}: {presentFailureClass(item.failure_class, locale)}
                {item.root_cause_class
                  ? ` · ${t("learning.cases.rootCause")}: ${presentFailureClass(item.root_cause_class, locale)}`
                  : null}
              </p>
              <p className="muted">{formatLearningTimestamp(item.created_at, locale)}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>{t("learning.candidates.title")}</h2>
        {candidates.length === 0 ? <p className="empty">{t("learning.candidates.empty")}</p> : null}
        <div className="stack" style={{ gap: 16, marginTop: 12 }}>
          {candidates.map((candidate) => {
            const risk = riskForCandidateType(candidate.candidate_type);
            const actionable = canReviewCandidate(candidate);
            return (
              <article key={candidate.id} className="card" aria-labelledby={`candidate-${candidate.id}`}>
                <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <h3 id={`candidate-${candidate.id}`}>{candidate.title}</h3>
                  <span className="badge">{presentCandidateStatus(candidate.status, locale)}</span>
                </div>
                <dl className="kv-list compact">
                  <div className="kv-row">
                    <dt>{t("learning.candidates.type")}</dt>
                    <dd>{presentCandidateType(candidate.candidate_type, locale)}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>{t("learning.candidates.risk")}</dt>
                    <dd>{presentRiskLevel(risk, locale)}</dd>
                  </div>
                  {candidate.promotion_verdict ? (
                    <div className="kv-row">
                      <dt>{t("learning.candidates.verdict")}</dt>
                      <dd>{presentPromotionVerdict(candidate.promotion_verdict, locale)}</dd>
                    </div>
                  ) : null}
                  <div className="kv-row">
                    <dt>{t("table.updated")}</dt>
                    <dd>{formatLearningTimestamp(candidate.created_at, locale)}</dd>
                  </div>
                </dl>
                {!demoReadOnly && actionable ? (
                  <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                    <button
                      className="btn primary"
                      disabled={busy === candidate.id}
                      onClick={() => void approveCandidate(candidate)}
                    >
                      {t("learning.actions.approve")}
                    </button>
                    <button
                      className="btn danger"
                      disabled={busy === candidate.id}
                      onClick={() => void rejectCandidate(candidate)}
                    >
                      {t("learning.actions.reject")}
                    </button>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>{t("learning.policies.title")}</h2>
        {activePolicies.length === 0 ? <p className="empty">{t("learning.policies.empty")}</p> : null}
        <div className="stack" style={{ gap: 12, marginTop: 12 }}>
          {activePolicies.map((policy) => (
            <article key={policy.id} className="card" style={{ padding: 12 }}>
              <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <strong>{policy.policy_key}</strong>
                <span className="badge run">{policy.version_label}</span>
              </div>
              {policy.promotion_reason ? <p className="wrap-text muted">{policy.promotion_reason}</p> : null}
              <p className="muted">{formatLearningTimestamp(policy.created_at, locale)}</p>
              {!demoReadOnly ? (
                <button
                  className="btn"
                  style={{ marginTop: 8 }}
                  disabled={busy === policy.id}
                  onClick={() => void rollbackPolicy(policy)}
                >
                  {t("learning.actions.rollback")}
                </button>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="technical-details" style={{ marginTop: 16 }}>
        <button
          type="button"
          className="technical-details-toggle"
          aria-expanded={auditOpen}
          onClick={() => setAuditOpen((value) => !value)}
        >
          <span>{t("learning.audit.title")}</span>
          <span aria-hidden="true">{auditOpen ? "−" : "+"}</span>
        </button>
        {auditOpen ? (
          audit.length === 0 ? (
            <p className="empty">{t("learning.audit.empty")}</p>
          ) : (
            <div className="stack" style={{ gap: 12, marginTop: 12 }}>
              {audit.map((event) => (
                <article key={event.id} className="card" style={{ padding: 12 }}>
                  <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{presentAuditEventType(event.event_type, locale)}</strong>
                    <span className="muted">{formatLearningTimestamp(event.created_at, locale)}</span>
                  </div>
                  {event.policy_key ? <p className="muted">{event.policy_key}</p> : null}
                  {event.previous_version_label || event.new_version_label ? (
                    <p className="muted">
                      {event.previous_version_label ?? "—"} → {event.new_version_label ?? "—"}
                    </p>
                  ) : null}
                  {event.reason ? <p className="wrap-text">{event.reason}</p> : null}
                  <p className="muted">
                    {t("learning.audit.actor")}: {event.actor_label}
                  </p>
                </article>
              ))}
            </div>
          )
        ) : null}
      </section>
    </div>
  );
}
