"""Learning effectiveness analytics — read-only aggregates, conservative attribution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from deepscout_persistence.store import ResearchStore

MIN_COHORT_SAMPLES = 5


class AttributionStrength(StrEnum):
    OBSERVED_ASSOCIATION = "observed_association"
    CONTROLLED_EXPERIMENT_SUPPORT = "controlled_experiment_support"
    STRONG_REGRESSION_EVIDENCE = "strong_regression_evidence"
    INCONCLUSIVE = "inconclusive"


class PolicyOutcomeVerdict(StrEnum):
    IMPROVED = "improved"
    NEUTRAL = "neutral"
    REGRESSED = "regressed"
    INCONCLUSIVE = "inconclusive"
    INSUFFICIENT_DATA = "insufficient_data"


class LearningHealthState(StrEnum):
    HEALTHY = "healthy"
    OBSERVING = "observing"
    INSUFFICIENT_DATA = "insufficient_data"
    REGRESSION_DETECTED = "regression_detected"
    ROLLBACK_RECOMMENDED = "rollback_recommended"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


@dataclass(frozen=True, slots=True)
class CohortMetrics:
    sample_count: int
    quality_mean: float | None
    cost_mean: float | None
    latency_mean: float | None
    failure_rate: float | None


@dataclass(frozen=True, slots=True)
class PolicyFamilyEffectiveness:
    policy_family: str
    policy_key: str
    version_label: str
    activated_at: datetime | None
    before: CohortMetrics
    after: CohortMetrics
    quality_delta: float | None
    cost_delta: float | None
    failure_recurrence_rate: float | None
    attribution: AttributionStrength
    verdict: PolicyOutcomeVerdict
    monitoring_samples: int = 0
    rolled_back: bool = False


@dataclass(frozen=True, slots=True)
class LearningDebt:
    unresolved_cases: int
    unevaluated_candidates: int
    stale_experiments: int
    pending_hitl_reviews: int
    incomplete_monitoring: int
    policies_insufficient_evidence: int


@dataclass(frozen=True, slots=True)
class LearningEffectivenessReport:
    health: LearningHealthState
    health_reason: str
    production_counts: dict[str, int]
    policy_win_rate: float | None
    rollback_rate: float | None
    false_promotion_rate: float | None
    mean_time_to_remediation_hours: float | None
    families: list[PolicyFamilyEffectiveness] = field(default_factory=list)
    debt: LearningDebt | None = None
    policy_drift_flags: list[str] = field(default_factory=list)
    experience_sample_count: int = 0
    opportunity_cases: int = 0
    user_feedback_cases: int = 0
    hitl_learning_cases: int = 0


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _run_quality(eval_rows: list[dict[str, Any]]) -> float | None:
    if not eval_rows:
        return None
    passed = sum(1 for row in eval_rows if str(row.get("status")) == "passed")
    return passed / len(eval_rows)


def _cohort_key(run: dict[str, Any]) -> str:
    return "|".join(
        [
            str(run.get("research_mode") or "unknown"),
            str(run.get("output_language") or "en"),
        ]
    )


def _policy_versions_in_run(run: dict[str, Any]) -> dict[str, str]:
    snapshot = run.get("config_snapshot") or {}
    block = snapshot.get("learning_policies") or {}
    out: dict[str, str] = {}
    for item in block.get("learning_policy_versions") or []:
        if isinstance(item, dict) and item.get("policy_family") and item.get("version_label"):
            out[str(item["policy_family"])] = str(item["version_label"])
    return out


def _compare_verdict(
    before: CohortMetrics,
    after: CohortMetrics,
    *,
    quality_delta: float | None,
) -> PolicyOutcomeVerdict:
    if before.sample_count < MIN_COHORT_SAMPLES or after.sample_count < MIN_COHORT_SAMPLES:
        return PolicyOutcomeVerdict.INSUFFICIENT_DATA
    if quality_delta is None:
        return PolicyOutcomeVerdict.INCONCLUSIVE
    if quality_delta >= 0.05:
        return PolicyOutcomeVerdict.IMPROVED
    if quality_delta <= -0.05:
        return PolicyOutcomeVerdict.REGRESSED
    return PolicyOutcomeVerdict.NEUTRAL


def compute_learning_effectiveness(
    store: ResearchStore,
    *,
    owner_principal_id: UUID | None,
) -> LearningEffectivenessReport:
    counts = store.get_learning_production_counts(owner_principal_id=owner_principal_id)
    runs = store.list_learning_analytics_runs(owner_principal_id=owner_principal_id, limit=400)
    policies = store.list_learning_policy_versions(
        owner_principal_id=owner_principal_id, active_only=True, limit=100
    )
    audit = store.list_learning_audit_events(owner_principal_id=owner_principal_id, limit=200)

    promoted = sum(1 for e in audit if e.get("event_type") == "policy_promoted")
    rolled = sum(
        1
        for e in audit
        if e.get("event_type") in {"policy_rolled_back", "policy_auto_rollback"}
    )
    win_rate = None
    rollback_rate = (rolled / promoted) if promoted else None

    family_reports: list[PolicyFamilyEffectiveness] = []
    drift_flags: list[str] = []

    for policy in policies:
        family = str(policy.get("policy_family") or "unknown")
        key = str(policy.get("policy_key"))
        version = str(policy.get("version_label"))
        activated = policy.get("activated_at") or policy.get("created_at")
        activated_dt = activated if isinstance(activated, datetime) else None

        before_quality: list[float] = []
        after_quality: list[float] = []
        before_cost: list[float] = []
        after_cost: list[float] = []
        before_latency: list[float] = []
        after_latency: list[float] = []
        before_failures = 0
        after_failures = 0

        for run in runs:
            versions = _policy_versions_in_run(run)
            if versions.get(family) != version:
                continue
            completed = run.get("completed_at")
            if completed is None or activated_dt is None:
                continue
            q = run.get("quality")
            if q is None:
                continue
            cost = float(run.get("consumed_tool_calls") or 0)
            latency = float(run.get("consumed_wall_time_seconds") or 0)
            failed = bool(run.get("had_critical_failure"))
            if completed < activated_dt:
                before_quality.append(float(q))
                before_cost.append(cost)
                before_latency.append(latency)
                before_failures += int(failed)
            else:
                after_quality.append(float(q))
                after_cost.append(cost)
                after_latency.append(latency)
                after_failures += int(failed)

        before = CohortMetrics(
            sample_count=len(before_quality),
            quality_mean=_mean(before_quality),
            cost_mean=_mean(before_cost),
            latency_mean=_mean(before_latency),
            failure_rate=(before_failures / len(before_quality)) if before_quality else None,
        )
        after = CohortMetrics(
            sample_count=len(after_quality),
            quality_mean=_mean(after_quality),
            cost_mean=_mean(after_cost),
            latency_mean=_mean(after_latency),
            failure_rate=(after_failures / len(after_quality)) if after_quality else None,
        )
        q_delta = None
        if before.quality_mean is not None and after.quality_mean is not None:
            q_delta = after.quality_mean - before.quality_mean
        c_delta = None
        if before.cost_mean is not None and after.cost_mean is not None:
            c_delta = after.cost_mean - before.cost_mean

        payload = policy.get("payload") or {}
        for knob, bounds in _drift_bounds_for_family(family):
            val = payload.get(knob)
            if val is None or not isinstance(bounds, tuple):
                continue
            lo, hi = bounds
            near_lo = val <= lo + 0.01 * (hi - lo)
            near_hi = val >= hi - 0.01 * (hi - lo)
            if isinstance(val, (int, float)) and (near_lo or near_hi):
                drift_flags.append(f"{family}:{knob} near bound ({val})")

        monitoring = store.get_policy_monitoring_for_key(
            policy_key=key, owner_principal_id=owner_principal_id
        )
        mon_samples = int((monitoring or {}).get("observed_samples", 0))

        family_reports.append(
            PolicyFamilyEffectiveness(
                policy_family=family,
                policy_key=key,
                version_label=version,
                activated_at=activated_dt,
                before=before,
                after=after,
                quality_delta=q_delta,
                cost_delta=c_delta,
                failure_recurrence_rate=after.failure_rate,
                attribution=AttributionStrength.OBSERVED_ASSOCIATION
                if after.sample_count >= MIN_COHORT_SAMPLES
                else AttributionStrength.INCONCLUSIVE,
                verdict=_compare_verdict(before, after, quality_delta=q_delta),
                monitoring_samples=mon_samples,
                rolled_back=any(
                    e.get("event_type") in {"policy_rolled_back", "policy_auto_rollback"}
                    and e.get("policy_key") == key
                    for e in audit
                ),
            )
        )

    improved = sum(1 for f in family_reports if f.verdict == PolicyOutcomeVerdict.IMPROVED)
    regressed = sum(1 for f in family_reports if f.verdict == PolicyOutcomeVerdict.REGRESSED)
    with_samples = [f for f in family_reports if f.after.sample_count >= MIN_COHORT_SAMPLES]
    if with_samples:
        win_rate = improved / len(with_samples)

    debt = LearningDebt(
        unresolved_cases=counts.get("cases_open", 0),
        unevaluated_candidates=max(
            0, counts.get("candidates_proposed", 0) - counts.get("candidates_evaluated", 0)
        ),
        stale_experiments=counts.get("experiments_pending", 0),
        pending_hitl_reviews=counts.get("candidates_requires_review", 0),
        incomplete_monitoring=counts.get("monitoring_active", 0),
        policies_insufficient_evidence=sum(
            1 for f in family_reports if f.verdict == PolicyOutcomeVerdict.INSUFFICIENT_DATA
        ),
    )

    health, reason = _derive_health(
        regressed=regressed,
        debt=debt,
        counts=counts,
        monitoring_active=counts.get("monitoring_active", 0),
    )

    return LearningEffectivenessReport(
        health=health,
        health_reason=reason,
        production_counts=counts,
        policy_win_rate=win_rate,
        rollback_rate=rollback_rate,
        false_promotion_rate=rollback_rate,
        mean_time_to_remediation_hours=None,
        families=family_reports,
        debt=debt,
        policy_drift_flags=drift_flags,
        experience_sample_count=counts.get("experience_samples", 0),
        opportunity_cases=counts.get("opportunity_cases", 0),
        user_feedback_cases=counts.get("user_feedback_cases", 0),
        hitl_learning_cases=counts.get("hitl_learning_cases", 0),
    )


def _derive_health(
    *,
    regressed: int,
    debt: LearningDebt,
    counts: dict[str, int],
    monitoring_active: int,
) -> tuple[LearningHealthState, str]:
    if regressed > 0:
        return (
            LearningHealthState.REGRESSION_DETECTED,
            "One or more active policies show quality regression",
        )
    if debt.pending_hitl_reviews > 0:
        return LearningHealthState.HUMAN_REVIEW_REQUIRED, "Candidates awaiting human review"
    if counts.get("terminal_runs", 0) < MIN_COHORT_SAMPLES:
        return (
            LearningHealthState.INSUFFICIENT_DATA,
            "Not enough terminal runs for cohort comparison",
        )
    if monitoring_active > 0:
        return LearningHealthState.OBSERVING, "Post-promotion monitoring windows active"
    if debt.unresolved_cases > 0 or debt.unevaluated_candidates > 0:
        return LearningHealthState.OBSERVING, "Open learning cases or unevaluated candidates"
    return LearningHealthState.HEALTHY, "No regression detected; learning debt low"


def _drift_bounds_for_family(family: str) -> list[tuple[str, tuple[float, float]]]:
    from deepscout_evaluation.learning.policy_families import FAMILY_BASELINES, PolicyFamily

    try:
        pf = PolicyFamily(family)
    except ValueError:
        return []
    keys = list(FAMILY_BASELINES.get(pf, {}).keys())
    from deepscout_evaluation.learning.policy_families import HARD_BOUNDS

    return [
        (k, HARD_BOUNDS[k])
        for k in keys
        if k in HARD_BOUNDS and isinstance(HARD_BOUNDS[k], tuple)
    ]


def effectiveness_to_dict(report: LearningEffectivenessReport) -> dict[str, Any]:
    return {
        "health": report.health.value,
        "health_reason": report.health_reason,
        "production_counts": report.production_counts,
        "policy_win_rate": report.policy_win_rate,
        "rollback_rate": report.rollback_rate,
        "experience_sample_count": report.experience_sample_count,
        "opportunity_cases": report.opportunity_cases,
        "user_feedback_cases": report.user_feedback_cases,
        "hitl_learning_cases": report.hitl_learning_cases,
        "policy_drift_flags": report.policy_drift_flags,
        "debt": {
            "unresolved_cases": report.debt.unresolved_cases,
            "unevaluated_candidates": report.debt.unevaluated_candidates,
            "stale_experiments": report.debt.stale_experiments,
            "pending_hitl_reviews": report.debt.pending_hitl_reviews,
            "incomplete_monitoring": report.debt.incomplete_monitoring,
            "policies_insufficient_evidence": report.debt.policies_insufficient_evidence,
        }
        if report.debt
        else None,
        "families": [
            {
                "policy_family": f.policy_family,
                "policy_key": f.policy_key,
                "version_label": f.version_label,
                "verdict": f.verdict.value,
                "attribution": f.attribution.value,
                "quality_delta": f.quality_delta,
                "cost_delta": f.cost_delta,
                "failure_recurrence_rate": f.failure_recurrence_rate,
                "monitoring_samples": f.monitoring_samples,
                "rolled_back": f.rolled_back,
                "before": {
                    "sample_count": f.before.sample_count,
                    "quality_mean": f.before.quality_mean,
                    "cost_mean": f.before.cost_mean,
                },
                "after": {
                    "sample_count": f.after.sample_count,
                    "quality_mean": f.after.quality_mean,
                    "cost_mean": f.after.cost_mean,
                },
            }
            for f in report.families
        ],
    }


@dataclass
class EffectivenessGateCase:
    case_id: str
    passed: bool
    detail: str = ""


@dataclass
class EffectivenessGateReport:
    passed: bool
    cases: list[EffectivenessGateCase] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "cases": [
                {"case_id": c.case_id, "passed": c.passed, "detail": c.detail} for c in self.cases
            ],
        }


def run_learning_effectiveness_gate() -> EffectivenessGateReport:
    """Deterministic analytics gate — zero provider spend, no DB required."""
    cases: list[EffectivenessGateCase] = []

    def cohort(n: int, q: float) -> CohortMetrics:
        return CohortMetrics(
            sample_count=n,
            quality_mean=q,
            cost_mean=10.0,
            latency_mean=30.0,
            failure_rate=0.1,
        )

    cases.append(
        EffectivenessGateCase(
            "A_clear_improvement",
            _compare_verdict(cohort(6, 0.6), cohort(6, 0.72), quality_delta=0.12)
            == PolicyOutcomeVerdict.IMPROVED,
            "quality delta +0.12",
        )
    )
    cases.append(
        EffectivenessGateCase(
            "B_clear_regression",
            _compare_verdict(cohort(6, 0.8), cohort(6, 0.6), quality_delta=-0.2)
            == PolicyOutcomeVerdict.REGRESSED,
            "quality delta -0.2",
        )
    )
    cases.append(
        EffectivenessGateCase(
            "C_same_quality_lower_cost",
            _compare_verdict(cohort(6, 0.7), cohort(6, 0.71), quality_delta=0.01)
            == PolicyOutcomeVerdict.NEUTRAL,
            "neutral quality within band",
        )
    )
    cases.append(
        EffectivenessGateCase(
            "D_insufficient_samples",
            _compare_verdict(cohort(2, 0.9), cohort(8, 0.5), quality_delta=-0.4)
            == PolicyOutcomeVerdict.INSUFFICIENT_DATA,
            "before cohort too small",
        )
    )
    cases.append(
        EffectivenessGateCase(
            "E_conflicting_metrics",
            _compare_verdict(cohort(6, 0.7), cohort(6, 0.69), quality_delta=-0.01)
            == PolicyOutcomeVerdict.NEUTRAL,
            "flat quality delta",
        )
    )
    debt = LearningDebt(1, 2, 0, 0, 1, 3)
    health, _ = _derive_health(
        regressed=0, debt=debt, counts={"terminal_runs": 2}, monitoring_active=0
    )
    cases.append(
        EffectivenessGateCase(
            "F_insufficient_terminal_runs",
            health == LearningHealthState.INSUFFICIENT_DATA,
            health.value,
        )
    )
    health_reg, _ = _derive_health(
        regressed=1, debt=debt, counts={"terminal_runs": 20}, monitoring_active=0
    )
    cases.append(
        EffectivenessGateCase(
            "G_regression_detected",
            health_reg == LearningHealthState.REGRESSION_DETECTED,
            health_reg.value,
        )
    )
    health_mon, _ = _derive_health(
        regressed=0, debt=debt, counts={"terminal_runs": 20}, monitoring_active=2
    )
    cases.append(
        EffectivenessGateCase(
            "H_monitoring_observing",
            health_mon == LearningHealthState.OBSERVING,
            health_mon.value,
        )
    )
    report = LearningEffectivenessReport(
        health=LearningHealthState.HEALTHY,
        health_reason="fixture",
        production_counts={},
        policy_win_rate=None,
        rollback_rate=None,
        false_promotion_rate=None,
        mean_time_to_remediation_hours=None,
    )
    payload = effectiveness_to_dict(report)
    cases.append(
        EffectivenessGateCase(
            "I_serialization",
            payload["health"] == "healthy" and payload["debt"] is None,
            "effectiveness_to_dict",
        )
    )
    cases.append(
        EffectivenessGateCase(
            "J_hitl_review_required",
            _derive_health(
                regressed=0,
                debt=LearningDebt(0, 0, 0, 1, 0, 0),
                counts={"terminal_runs": 20},
                monitoring_active=0,
            )[0]
            == LearningHealthState.HUMAN_REVIEW_REQUIRED,
            "pending HITL",
        )
    )
    passed = all(c.passed for c in cases)
    return EffectivenessGateReport(passed=passed, cases=cases)
