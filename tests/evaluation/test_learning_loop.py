"""Tests for continuous learning loop — deterministic, no provider spend."""

from __future__ import annotations

from deepscout_evaluation.learning.candidates import generate_improvement_candidate
from deepscout_evaluation.learning.diagnosis import diagnose_learning_case
from deepscout_evaluation.learning.experiment import run_experiment
from deepscout_evaluation.learning.failure_taxonomy import (
    FailureClass,
    earliest_root_cause,
    from_evaluator_failure,
    is_downstream_symptom,
)
from deepscout_evaluation.learning.loop import run_learning_loop_gate
from deepscout_evaluation.learning.models import (
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    PromotionVerdict,
    TrustLevel,
)
from deepscout_evaluation.learning.observation import observe_from_evaluations
from deepscout_evaluation.learning.policy import (
    DEFAULT_BASELINE_POLICY,
    gap_queries_per_round_bonus,
)
from deepscout_evaluation.learning.promotion import evaluate_promotion
from deepscout_evaluation.learning.trust import validate_learning_payload
from deepscout_evaluation.regression_origins import RegressionOrigin


def test_failure_taxonomy_prefers_upstream_root() -> None:
    root = earliest_root_cause(
        [FailureClass.SYNTHESIS_FAILURE, FailureClass.RETRIEVAL_FAILURE, FailureClass.CLAIM_FAILURE]
    )
    assert root == FailureClass.RETRIEVAL_FAILURE
    assert is_downstream_symptom(FailureClass.SYNTHESIS_FAILURE, FailureClass.RETRIEVAL_FAILURE)


def test_evaluator_failure_mapping() -> None:
    assert from_evaluator_failure("claim_has_evidence") == FailureClass.CLAIM_FAILURE
    assert from_evaluator_failure("dag_valid") == FailureClass.PLANNING_FAILURE


def test_observe_failure_from_evaluations() -> None:
    case = observe_from_evaluations(
        case_id="test-observe",
        evaluation_rows=[
            {"evaluator_id": "claim_has_evidence", "status": "failed"},
            {"evaluator_id": "budget_compliance", "status": "passed"},
        ],
        origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
    )
    assert case is not None
    assert case.failure_class == FailureClass.CLAIM_FAILURE.value


def test_demo_runs_do_not_create_learning_cases() -> None:
    case = observe_from_evaluations(
        case_id="demo-block",
        evaluation_rows=[{"evaluator_id": "claim_has_evidence", "status": "failed"}],
        is_public_demo=True,
    )
    assert case is None


def test_diagnose_upstream_retrieval_root() -> None:
    case = LearningCase(
        case_id="diag",
        subsystem=LearningSubsystem.SYNTHESIS,
        failure_class=FailureClass.SYNTHESIS_FAILURE.value,
        symptom="weak report",
        expected_behavior="supported claims",
        observed_behavior="missing evidence",
        diagnostic_evidence={
            "retrieval_failure_class": "routing_failure",
            "final_critic_verdict": "BLOCKED_BY_EVIDENCE",
        },
        evaluator_signals={"claim_has_evidence": "failed"},
    )
    diagnosed = diagnose_learning_case(case)
    assert diagnosed.root_cause_class == FailureClass.RETRIEVAL_FAILURE.value
    assert diagnosed.review_state == LearningCaseReviewState.DIAGNOSED


def test_poisoned_learning_payload_rejected() -> None:
    secret = "Bearer " + "x" * 24
    errors = validate_learning_payload(
        {
            "origin": RegressionOrigin.PRODUCTION_CANDIDATE.value,
            "symptom": secret,
            "observed_behavior": "leak",
        },
        required_trust=TrustLevel.REVIEWED_CASE,
    )
    assert errors


def test_promotion_rejects_security_regression() -> None:
    case = LearningCase(
        case_id="cov",
        subsystem=LearningSubsystem.COVERAGE,
        failure_class=FailureClass.COVERAGE_FAILURE.value,
        symptom="gap",
        expected_behavior="coverage",
        observed_behavior="gap remains",
        root_cause_class=FailureClass.COVERAGE_FAILURE.value,
    )
    candidate = generate_improvement_candidate(case)
    assert candidate is not None
    experiment = run_experiment(
        case_id="cov",
        baseline_policy=dict(DEFAULT_BASELINE_POLICY),
        candidate=candidate,
        fixture={
            "failure_class": "coverage_failure",
            "baseline_quality": 0.72,
            "scenario": "security_regression",
        },
    )
    decision = evaluate_promotion(candidate, experiment)
    assert decision.verdict == PromotionVerdict.REJECTED


def test_promotion_improves_with_human_approval() -> None:
    case = LearningCase(
        case_id="cov2",
        subsystem=LearningSubsystem.COVERAGE,
        failure_class=FailureClass.COVERAGE_FAILURE.value,
        symptom="gap",
        expected_behavior="coverage",
        observed_behavior="gap remains",
        root_cause_class=FailureClass.COVERAGE_FAILURE.value,
    )
    candidate = generate_improvement_candidate(case)
    assert candidate is not None
    experiment = run_experiment(
        case_id="cov2",
        baseline_policy=dict(DEFAULT_BASELINE_POLICY),
        candidate=candidate,
        fixture={
            "failure_class": "coverage_failure",
            "baseline_quality": 0.72,
            "coverage_score": 0.65,
        },
    )
    decision = evaluate_promotion(candidate, experiment, human_approved=True)
    assert decision.verdict == PromotionVerdict.SAFE_TO_PROMOTE
    assert gap_queries_per_round_bonus({**DEFAULT_BASELINE_POLICY, **candidate.policy_delta}) == 1


def test_learning_loop_gate_passes() -> None:
    report = run_learning_loop_gate()
    assert report.passed
    assert len(report.cases) >= 8
