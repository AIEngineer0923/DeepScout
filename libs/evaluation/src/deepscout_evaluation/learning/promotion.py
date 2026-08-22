"""Pareto-aware promotion policy with family risk classification."""

from __future__ import annotations

from deepscout_evaluation.learning.models import (
    ExperimentComparison,
    ExperimentOutcome,
    ImprovementCandidate,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
    PromotionDecision,
    PromotionVerdict,
    TrustLevel,
)
from deepscout_evaluation.learning.policy import risk_for_family
from deepscout_evaluation.learning.policy_families import (
    PolicyFamily,
    PolicyRiskLevel,
    family_for_payload_delta,
)
from deepscout_evaluation.learning.trust import trust_meets_minimum

_HIGH_IMPACT_TYPES = frozenset(
    {
        ImprovementCandidateType.PROMPT,
        ImprovementCandidateType.PLANNER_POLICY,
        ImprovementCandidateType.WORKER_POLICY,
        ImprovementCandidateType.CODE_PROPOSAL,
        ImprovementCandidateType.SYNTHESIS_POLICY,
    }
)

_MAX_COST_DELTA_AUTO = 0.15
_MAX_LATENCY_DELTA_MS = 500.0
_MIN_SAMPLE_COUNT = 2


def _family_for_candidate(candidate: ImprovementCandidate) -> PolicyFamily:
    family = family_for_payload_delta(candidate.policy_delta)
    if family is not None:
        return family
    mapping = {
        ImprovementCandidateType.COVERAGE_POLICY: PolicyFamily.CORRECTIVE_RESEARCH,
        ImprovementCandidateType.RETRIEVAL_PARAMETER: PolicyFamily.RETRIEVAL,
        ImprovementCandidateType.QUERY_STRATEGY: PolicyFamily.QUERY_STRATEGY,
        ImprovementCandidateType.PLANNER_POLICY: PolicyFamily.PLANNER,
        ImprovementCandidateType.WORKER_POLICY: PolicyFamily.ALLOCATION,
        ImprovementCandidateType.STOPPING_POLICY: PolicyFamily.SUFFICIENCY,
        ImprovementCandidateType.SYNTHESIS_POLICY: PolicyFamily.SYNTHESIS,
        ImprovementCandidateType.CONFIGURATION: PolicyFamily.COST_LATENCY,
    }
    return mapping.get(candidate.candidate_type, PolicyFamily.CORRECTIVE_RESEARCH)


def evaluate_promotion(
    candidate: ImprovementCandidate,
    experiment: ExperimentComparison,
    *,
    human_approved: bool = False,
    min_quality_improvement: float = 0.02,
    sample_count: int = 1,
    cooldown_active: bool = False,
) -> PromotionDecision:
    reasons: list[str] = []
    family = _family_for_candidate(candidate)
    risk = risk_for_family(family)

    if not trust_meets_minimum(candidate.trust_level, TrustLevel.SANITIZED_CANDIDATE):
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REJECTED,
            outcome=experiment.outcome,
            reasons=["trust level too low"],
            requires_human=False,
        )

    if len(candidate.policy_delta) > 3:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REQUIRES_HUMAN_REVIEW,
            outcome=experiment.outcome,
            reasons=["multi-knob candidate requires human review"],
            requires_human=True,
        )

    if experiment.security_regressed:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REJECTED,
            outcome=ExperimentOutcome.REGRESSED,
            reasons=["security regression detected"],
            requires_human=False,
        )

    if experiment.outcome == ExperimentOutcome.REGRESSED:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REJECTED,
            outcome=experiment.outcome,
            reasons=["candidate regressed on measured dimensions"],
            requires_human=False,
        )

    if experiment.outcome == ExperimentOutcome.INCONCLUSIVE:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.NO_CHANGE,
            outcome=experiment.outcome,
            reasons=["inconclusive experiment — default no change"],
            requires_human=False,
        )

    if cooldown_active:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.NO_CHANGE,
            outcome=experiment.outcome,
            reasons=["promotion cooldown active — anti-oscillation"],
            requires_human=False,
        )

    requires_human = (
        risk == PolicyRiskLevel.HIGH_RISK_HUMAN_ONLY
        or risk == PolicyRiskLevel.MEDIUM_RISK_HITL
        or candidate.candidate_type in _HIGH_IMPACT_TYPES
        or bool(candidate.evaluation_plan.get("requires_human"))
        or experiment.cost_delta > _MAX_COST_DELTA_AUTO
        or experiment.latency_delta > _MAX_LATENCY_DELTA_MS
    )

    if risk == PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE and not bool(
        candidate.evaluation_plan.get("requires_human")
    ):
        requires_human = requires_human and candidate.candidate_type in _HIGH_IMPACT_TYPES

    if experiment.outcome == ExperimentOutcome.NEUTRAL:
        if requires_human and not human_approved:
            return PromotionDecision(
                candidate_id=candidate.candidate_id,
                verdict=PromotionVerdict.REQUIRES_HUMAN_REVIEW,
                outcome=experiment.outcome,
                reasons=["neutral outcome but human review required for policy family"],
                requires_human=True,
            )
        pareto_ok = experiment.cost_delta < -0.05 or experiment.latency_delta < -50
        if not pareto_ok:
            return PromotionDecision(
                candidate_id=candidate.candidate_id,
                verdict=PromotionVerdict.NO_CHANGE,
                outcome=experiment.outcome,
                reasons=["neutral outcome — no promotion"],
                requires_human=requires_human,
            )

    if (
        experiment.quality_delta < min_quality_improvement
        and experiment.outcome != ExperimentOutcome.IMPROVED
        and experiment.cost_delta >= 0
    ):
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.NO_CHANGE,
            outcome=experiment.outcome,
            reasons=["quality improvement below threshold"],
            requires_human=False,
        )

    if sample_count < _MIN_SAMPLE_COUNT and risk != PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REQUIRES_HUMAN_REVIEW,
            outcome=experiment.outcome,
            reasons=[f"insufficient samples ({sample_count} < {_MIN_SAMPLE_COUNT})"],
            requires_human=True,
        )

    if requires_human and not human_approved:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REQUIRES_HUMAN_REVIEW,
            outcome=experiment.outcome,
            reasons=["change requires human approval"],
            requires_human=True,
        )

    if experiment.outcome == ExperimentOutcome.IMPROVED or (
        experiment.cost_delta < -0.05 and not experiment.security_regressed
    ):
        candidate.status = ImprovementCandidateStatus.APPROVED
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.SAFE_TO_PROMOTE,
            outcome=experiment.outcome,
            reasons=["improved without security regression"],
            requires_human=False,
            policy_version_label=f"learning-{family.value}-v1",
        )

    return PromotionDecision(
        candidate_id=candidate.candidate_id,
        verdict=PromotionVerdict.NO_CHANGE,
        outcome=experiment.outcome,
        reasons=reasons or ["default no change"],
        requires_human=requires_human,
    )
