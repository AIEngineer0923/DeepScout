"""End-to-end learning loop runner for deterministic fixtures and CI gate."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepscout_evaluation.learning.candidates import generate_improvement_candidate
from deepscout_evaluation.learning.diagnosis import diagnose_learning_case
from deepscout_evaluation.learning.experiment import run_experiment
from deepscout_evaluation.learning.failure_taxonomy import FailureClass
from deepscout_evaluation.learning.models import (
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    PromotionVerdict,
    TrustLevel,
)
from deepscout_evaluation.learning.observation import (
    observe_from_evaluations,
    observe_opportunity_from_metrics,
)
from deepscout_evaluation.learning.policy import (
    DEFAULT_BASELINE_POLICY,
    apply_promotion,
    gap_queries_per_round_bonus,
    rollback_policy,
)
from deepscout_evaluation.learning.promotion import evaluate_promotion
from deepscout_evaluation.learning.trust import validate_learning_payload
from deepscout_evaluation.regression_origins import RegressionOrigin

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
FIXTURE_PATH = _DATA_DIR / "learning_loop_deterministic_v1.json"


@dataclass
class LoopCaseResult:
    case_id: str
    stage: str
    passed: bool
    detail: str = ""
    failure_class: str | None = None


@dataclass
class LoopGateReport:
    passed: bool
    cases: list[LoopCaseResult] = field(default_factory=list)
    policy_after_promotion: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "cases": [
                {
                    "case_id": item.case_id,
                    "stage": item.stage,
                    "passed": item.passed,
                    "detail": item.detail,
                    "failure_class": item.failure_class,
                }
                for item in self.cases
            ],
            "policy_after_promotion": self.policy_after_promotion,
        }


def load_fixture(path: Path | None = None) -> dict[str, Any]:
    target = path or FIXTURE_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def run_learning_loop_case(case: dict[str, Any]) -> LoopCaseResult:
    case_id = str(case["case_id"])
    stage = str(case.get("stage", "full_loop"))
    baseline = dict(case.get("baseline_policy", DEFAULT_BASELINE_POLICY))

    if stage == "poison_reject":
        errors = validate_learning_payload(
            case["payload"], required_trust=TrustLevel.REVIEWED_CASE
        )
        passed = len(errors) > 0
        return LoopCaseResult(case_id, stage, passed, "; ".join(errors) or "should reject")

    if stage == "observe_failure":
        observed = observe_from_evaluations(
            case_id=case_id,
            evaluation_rows=case["evaluation_rows"],
            config_snapshot=case.get("config_snapshot"),
            origin=RegressionOrigin(case.get("origin", "development_synthetic")),
            is_public_demo=case.get("is_public_demo", False),
        )
        passed = observed is not None and observed.failure_class == case.get(
            "expected_failure_class"
        )
        return LoopCaseResult(
            case_id,
            stage,
            passed,
            f"failure_class={observed.failure_class if observed else None}",
            failure_class=case.get("expected_failure_class"),
        )

    if stage == "observe_demo_blocked":
        observed = observe_from_evaluations(
            case_id=case_id,
            evaluation_rows=case["evaluation_rows"],
            is_public_demo=True,
        )
        return LoopCaseResult(case_id, stage, observed is None, "demo must not create cases")

    if stage == "diagnose_upstream":
        learning_case = LearningCase(
            case_id=case_id,
            subsystem=LearningSubsystem.SYNTHESIS,
            failure_class=FailureClass.SYNTHESIS_FAILURE.value,
            symptom=case["symptom"],
            expected_behavior=case["expected_behavior"],
            observed_behavior=case["observed_behavior"],
            origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
            diagnostic_evidence=case.get("diagnostic_evidence", {}),
            evaluator_signals=case.get("evaluator_signals", {}),
        )
        diagnosed = diagnose_learning_case(learning_case)
        passed = diagnosed.root_cause_class == case.get("expected_root_cause")
        return LoopCaseResult(
            case_id,
            stage,
            passed,
            f"root={diagnosed.root_cause_class}",
            failure_class=diagnosed.root_cause_class,
        )

    if stage == "opportunity_detect":
        opp = observe_opportunity_from_metrics(
            case_id=case_id,
            strategy_a=case["strategy_a"],
            strategy_b=case["strategy_b"],
            min_samples=case.get("min_samples", 5),
            sample_count=case.get("sample_count", 0),
        )
        expect = case.get("expect_opportunity", True)
        passed = (opp is not None) == expect
        return LoopCaseResult(case_id, stage, passed, f"opportunity={opp is not None}")

    if stage == "full_loop":
        learning_case = LearningCase(
            case_id=case_id,
            subsystem=LearningSubsystem(case["subsystem"]),
            failure_class=case["failure_class"],
            symptom=case["symptom"],
            expected_behavior=case["expected_behavior"],
            observed_behavior=case["observed_behavior"],
            origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
            trust_level=TrustLevel.VALIDATED_LEARNING,
            review_state=LearningCaseReviewState.DIAGNOSED,
            sanitized=True,
            root_cause_class=case.get("root_cause_class", case["failure_class"]),
            diagnostic_evidence=case.get("fixture", {}),
        )
        candidate = generate_improvement_candidate(learning_case)
        if candidate is None:
            return LoopCaseResult(case_id, stage, False, "no candidate generated")
        experiment = run_experiment(
            case_id=case_id,
            baseline_policy=baseline,
            candidate=candidate,
            fixture=case.get("fixture", {}),
        )
        decision = evaluate_promotion(
            candidate,
            experiment,
            human_approved=case.get("human_approved", False),
        )
        expected_verdict = PromotionVerdict(case["expected_verdict"])
        passed = decision.verdict == expected_verdict
        detail = f"verdict={decision.verdict.value} outcome={experiment.outcome.value}"
        policy_after = None
        if decision.verdict == PromotionVerdict.SAFE_TO_PROMOTE:
            promoted = apply_promotion(decision, candidate.policy_delta)
            if promoted:
                policy_after = promoted.payload
                bonus = gap_queries_per_round_bonus(policy_after)
                if case.get("expect_runtime_bonus") is not None:
                    passed = passed and bonus == case["expect_runtime_bonus"]
        return LoopCaseResult(
            case_id,
            stage,
            passed,
            detail,
            failure_class=experiment.outcome.value,
        )

    if stage == "rollback":
        from deepscout_evaluation.learning.models import PolicyVersion

        active = PolicyVersion(
            policy_key="global.corrective_research",
            version_label="test-v1",
            payload={**DEFAULT_BASELINE_POLICY, "gap_queries_per_round_bonus": 1},
            active=True,
        )
        rolled = rollback_policy(active)
        passed = rolled.payload == DEFAULT_BASELINE_POLICY
        return LoopCaseResult(case_id, stage, passed, "rollback to baseline")

    return LoopCaseResult(case_id, stage, False, f"unknown stage {stage}")


def run_learning_loop_gate(fixture_path: Path | None = None) -> LoopGateReport:
    fixture = load_fixture(fixture_path)
    results = [run_learning_loop_case(case) for case in fixture.get("cases", [])]
    passed = all(item.passed for item in results)
    policy_after: dict[str, Any] | None = None
    for item in results:
        if item.stage == "full_loop" and item.passed and "SAFE_TO_PROMOTE" in item.detail:
            # last promoted policy from fixture cases
            pass
    # extract policy from improved case if any
    for case in fixture.get("cases", []):
        if case.get("expected_verdict") == "safe_to_promote":
            learning_case = LearningCase(
                case_id=case["case_id"],
                subsystem=LearningSubsystem(case["subsystem"]),
                failure_class=case["failure_class"],
                symptom=case["symptom"],
                expected_behavior=case["expected_behavior"],
                observed_behavior=case["observed_behavior"],
                origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
                root_cause_class=case.get("root_cause_class", case["failure_class"]),
            )
            candidate = generate_improvement_candidate(learning_case)
            if candidate:
                experiment = run_experiment(
                    case_id=case["case_id"],
                    baseline_policy=case.get("baseline_policy", DEFAULT_BASELINE_POLICY),
                    candidate=candidate,
                    fixture=case.get("fixture", {}),
                )
                decision = evaluate_promotion(candidate, experiment, human_approved=True)
                promoted = apply_promotion(decision, candidate.policy_delta)
                if promoted:
                    policy_after = promoted.payload

    return LoopGateReport(passed=passed, cases=results, policy_after_promotion=policy_after)
