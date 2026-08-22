"""Pareto-aware promotion policy — no simplistic score threshold."""

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
from deepscout_evaluation.learning.trust import trust_meets_minimum

_HIGH_IMPACT_TYPES = frozenset(
    {
        ImprovementCandidateType.PROMPT,
        ImprovementCandidateType.PLANNER_POLICY,
        ImprovementCandidateType.WORKER_POLICY,
        ImprovementCandidateType.CODE_PROPOSAL,
    }
)


def evaluate_promotion(
    candidate: ImprovementCandidate,
    experiment: ExperimentComparison,
    *,
    human_approved: bool = False,
    min_quality_improvement: float = 0.02,
) -> PromotionDecision:
    reasons: list[str] = []

    if not trust_meets_minimum(candidate.trust_level, TrustLevel.SANITIZED_CANDIDATE):
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REJECTED,
            outcome=experiment.outcome,
            reasons=["trust level too low"],
            requires_human=False,
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

    requires_human = (
        candidate.candidate_type in _HIGH_IMPACT_TYPES
        or bool(candidate.evaluation_plan.get("requires_human"))
        or experiment.cost_delta > 0.15
    )

    if experiment.outcome == ExperimentOutcome.NEUTRAL:
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
    ):
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.NO_CHANGE,
            outcome=experiment.outcome,
            reasons=["quality improvement below threshold"],
            requires_human=False,
        )

    if requires_human and not human_approved:
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.REQUIRES_HUMAN_REVIEW,
            outcome=experiment.outcome,
            reasons=["high-impact change requires human approval"],
            requires_human=True,
        )

    if experiment.outcome == ExperimentOutcome.IMPROVED:
        candidate.status = ImprovementCandidateStatus.APPROVED
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            verdict=PromotionVerdict.SAFE_TO_PROMOTE,
            outcome=experiment.outcome,
            reasons=["improved without security regression"],
            requires_human=False,
            policy_version_label="learning-policy-v1",
        )

    return PromotionDecision(
        candidate_id=candidate.candidate_id,
        verdict=PromotionVerdict.NO_CHANGE,
        outcome=experiment.outcome,
        reasons=reasons or ["default no change"],
        requires_human=requires_human,
    )
