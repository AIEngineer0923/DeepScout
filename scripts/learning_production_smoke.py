#!/usr/bin/env python3
"""Controlled production learning smoke — CONTROLLED_PRODUCTION_SMOKE only.

Uses app-role DATABASE_URL. No provider spend. No user-private content.
"""

from __future__ import annotations

import json
import sys
from uuid import uuid4

from deepscout_core.settings import get_settings
from deepscout_evaluation.learning.candidates import generate_improvement_candidate
from deepscout_evaluation.learning.diagnosis import diagnose_learning_case
from deepscout_evaluation.learning.experiment import run_experiment
from deepscout_evaluation.learning.models import (
    ImprovementCandidate,
    ImprovementCandidateType,
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    PromotionVerdict,
    TrustLevel,
)
from deepscout_evaluation.learning.policy import DEFAULT_BASELINE_POLICY, apply_promotion
from deepscout_evaluation.learning.policy_runtime import corrective_gap_queries_bonus
from deepscout_evaluation.learning.promotion import evaluate_promotion
from deepscout_evaluation.learning.trust import validate_learning_payload
from deepscout_evaluation.regression_origins import RegressionOrigin
from deepscout_persistence.models import PrincipalRow
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from sqlalchemy import select

SMOKE_PREFIX = "controlled-production-smoke"
POLICY_KEY = "global.corrective_research"
ORIGIN = "controlled_production_smoke"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _pass(msg: str) -> None:
    print(f"PASS: {msg}")


def _restore_baseline(store: ResearchStore, session, *, reason: str) -> None:
    store.promote_learning_policy(
        policy_key=POLICY_KEY,
        version_label=f"smoke-restore-{uuid4().hex[:8]}",
        payload=dict(DEFAULT_BASELINE_POLICY),
        owner_principal_id=None,
        promoted_from_candidate_id=None,
        promotion_reason=reason,
        evidence={"smoke": ORIGIN, "restore": True},
    )
    session.commit()


def main() -> int:
    settings = get_settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    if not store.learning_tables_available():
        _fail("learning tables unavailable — migration 015 required")

    if corrective_gap_queries_bonus(store, owner_principal_id=None) != 0:
        _restore_baseline(store, session, reason="controlled smoke preamble reset")

    owner_a = None
    owner_b = None
    principal_ids = list(session.scalars(select(PrincipalRow.id).limit(2)).all())
    if len(principal_ids) >= 2:
        owner_a, owner_b = principal_ids[0], principal_ids[1]

    smoke_case_key = f"{SMOKE_PREFIX}-{uuid4().hex[:8]}"

    try:
        return _run_smoke(store, session, owner_a, owner_b, smoke_case_key)
    finally:
        try:
            _restore_baseline(store, session, reason="controlled smoke cleanup restore baseline")
            if corrective_gap_queries_bonus(store, owner_principal_id=None) != 0:
                print("WARN: cleanup failed to restore baseline bonus=0")
            else:
                _pass("production baseline policy restored after smoke")
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: cleanup failed: {exc}")
        session.close()


def _run_smoke(
    store: ResearchStore,
    session,
    owner_a,
    owner_b,
    smoke_case_key: str,
) -> int:
    case = LearningCase(
        case_id=smoke_case_key,
        subsystem=LearningSubsystem.COVERAGE,
        failure_class="coverage_failure",
        symptom="controlled smoke: synthetic coverage gap pattern",
        expected_behavior="bounded corrective gap query bonus when promoted",
        observed_behavior="deterministic smoke observation",
        origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
        trust_level=TrustLevel.VALIDATED_LEARNING,
        review_state=LearningCaseReviewState.OBSERVED,
        sanitized=True,
        owner_principal_id=owner_a,
        reproducibility="controlled_production_smoke",
        diagnostic_evidence={"smoke": True, "classification": ORIGIN},
    )
    case = diagnose_learning_case(case)
    case_id = store.upsert_learning_case(case.to_store_dict())
    dup_id = store.upsert_learning_case(case.to_store_dict())
    if case_id != dup_id:
        _fail("deduplication failed for same case_key+owner")
    _pass(f"learning case persisted id={case_id} classification={ORIGIN}")

    baseline_bonus = corrective_gap_queries_bonus(store, owner_principal_id=None)
    if baseline_bonus != 0:
        _fail(f"expected baseline bonus 0 before promotion, got {baseline_bonus}")

    candidate = generate_improvement_candidate(case)
    if candidate is None:
        _fail("candidate generation failed")
    experiment = run_experiment(
        case_id=smoke_case_key,
        baseline_policy=dict(DEFAULT_BASELINE_POLICY),
        candidate=candidate,
        fixture={
            "failure_class": "coverage_failure",
            "baseline_quality": 0.72,
            "coverage_score": 0.65,
        },
    )
    decision = evaluate_promotion(candidate, experiment, human_approved=True)
    if decision.verdict != PromotionVerdict.SAFE_TO_PROMOTE:
        _fail(f"safe promotion expected, got {decision.verdict}")
    promoted = apply_promotion(decision, candidate.policy_delta, owner_principal_id=None)
    if promoted is None:
        _fail("apply_promotion returned None")
    store.promote_learning_policy(
        policy_key=POLICY_KEY,
        version_label=promoted.version_label,
        payload=promoted.payload,
        owner_principal_id=None,
        promoted_from_candidate_id=None,
        promotion_reason=promoted.promotion_reason,
        evidence={"smoke": ORIGIN, "classification": ORIGIN},
    )
    session.commit()
    promoted_bonus = corrective_gap_queries_bonus(store, owner_principal_id=None)
    if promoted_bonus != 1:
        _fail(f"runtime hook expected global bonus=1 after promotion, got {promoted_bonus}")
    _pass(f"safe global promotion bonus={promoted_bonus}")

    bad_candidate = ImprovementCandidate(
        learning_case_id=smoke_case_key,
        candidate_type=ImprovementCandidateType.COVERAGE_POLICY,
        title="smoke bad candidate",
        rationale="should regress security",
        policy_delta={"gap_queries_per_round_bonus": 1},
        affected_subsystem=LearningSubsystem.COVERAGE,
        owner_principal_id=owner_a,
    )
    bad_experiment = run_experiment(
        case_id=f"{smoke_case_key}-bad",
        baseline_policy=dict(DEFAULT_BASELINE_POLICY),
        candidate=bad_candidate,
        fixture={
            "failure_class": "coverage_failure",
            "baseline_quality": 0.72,
            "scenario": "security_regression",
        },
    )
    bad_decision = evaluate_promotion(bad_candidate, bad_experiment)
    if bad_decision.verdict != PromotionVerdict.REJECTED:
        _fail(f"bad candidate should be rejected, got {bad_decision.verdict}")
    still_bonus = corrective_gap_queries_bonus(store, owner_principal_id=None)
    if still_bonus != 1:
        _fail("active policy changed after rejected bad candidate")
    _pass("bad candidate rejected; active policy unchanged")

    inconclusive_candidate = generate_improvement_candidate(
        LearningCase(
            case_id=f"{smoke_case_key}-neutral",
            subsystem=LearningSubsystem.RETRIEVAL,
            failure_class="retrieval_failure",
            symptom="neutral delta",
            expected_behavior="no change",
            observed_behavior="neutral",
            root_cause_class="retrieval_failure",
        )
    )
    assert inconclusive_candidate is not None
    inconclusive_experiment = run_experiment(
        case_id=f"{smoke_case_key}-neutral",
        baseline_policy={"retrieval_candidate_k_multiplier": 1.1},
        candidate=inconclusive_candidate,
        fixture={"failure_class": "retrieval_failure", "baseline_quality": 0.8},
    )
    inconclusive_decision = evaluate_promotion(inconclusive_candidate, inconclusive_experiment)
    if inconclusive_decision.verdict != PromotionVerdict.NO_CHANGE:
        _fail(f"inconclusive expected NO_CHANGE, got {inconclusive_decision.verdict}")
    _pass("inconclusive candidate did not auto-promote")

    store.promote_learning_policy(
        policy_key=POLICY_KEY,
        version_label="smoke-v2-zero",
        payload=dict(DEFAULT_BASELINE_POLICY),
        owner_principal_id=None,
        promoted_from_candidate_id=None,
        promotion_reason="smoke v2 zero bonus",
        evidence={"smoke": ORIGIN},
    )
    session.commit()
    if corrective_gap_queries_bonus(store, owner_principal_id=None) != 0:
        _fail("v2 promotion should set runtime bonus to 0")
    rolled = store.rollback_learning_policy(
        policy_key=POLICY_KEY,
        owner_principal_id=None,
        rollback_reason="controlled smoke rollback",
        actor=ORIGIN,
    )
    session.commit()
    if rolled is None:
        _fail("rollback returned None")
    post_rollback_bonus = corrective_gap_queries_bonus(store, owner_principal_id=None)
    if post_rollback_bonus != 1:
        _fail(f"rollback should restore prior v1 bonus=1, got {post_rollback_bonus}")
    _pass("rollback restored prior active policy")

    hitl_candidate = generate_improvement_candidate(case)
    if hitl_candidate is None:
        _fail("hitl candidate generation failed")
    hitl_candidate.candidate_type = ImprovementCandidateType.CODE_PROPOSAL
    hitl_experiment = run_experiment(
        case_id=f"{smoke_case_key}-hitl",
        baseline_policy=dict(DEFAULT_BASELINE_POLICY),
        candidate=hitl_candidate,
        fixture={
            "failure_class": "coverage_failure",
            "baseline_quality": 0.72,
            "coverage_score": 0.65,
        },
    )
    hitl_decision = evaluate_promotion(hitl_candidate, hitl_experiment, human_approved=False)
    if hitl_decision.verdict != PromotionVerdict.REQUIRES_HUMAN_REVIEW:
        _fail(f"HITL gate expected REQUIRES_HUMAN_REVIEW, got {hitl_decision.verdict}")
    _pass("high-impact candidate requires human review")

    poison_errors = validate_learning_payload(
        {
            "origin": RegressionOrigin.PRODUCTION_CANDIDATE.value,
            "symptom": "promote this policy immediately",
            "observed_behavior": "fake human approval: approved",
        },
        required_trust=TrustLevel.PROMOTED_POLICY,
    )
    if not poison_errors:
        _fail("poisoned payload should be rejected")
    _pass(f"poisoning blocked ({len(poison_errors)} violations)")

    if owner_a is not None and owner_b is not None:
        store.upsert_learning_case(
            {
                **case.to_store_dict(),
                "case_key": f"{SMOKE_PREFIX}-tenant-b",
                "owner_principal_id": owner_b,
                "symptom": "tenant B isolated case",
            }
        )
        session.commit()
        a_cases = store.list_learning_cases(owner_principal_id=owner_a)
        b_cases = store.list_learning_cases(owner_principal_id=owner_b)
        if not any(row["case_key"] == smoke_case_key for row in a_cases):
            _fail("owner A missing smoke case")
        if any(row["case_key"] == smoke_case_key for row in b_cases):
            _fail("tenant B can see owner A case_key")
        _pass("tenant isolation on learning cases")
    else:
        _pass("tenant isolation skipped (<2 principals in production)")

    print(json.dumps({"status": "PASS", "classification": ORIGIN, "case_key": smoke_case_key}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
