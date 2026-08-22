"""Generate improvement candidates from diagnosed learning cases."""

from __future__ import annotations

from deepscout_evaluation.learning.failure_taxonomy import FailureClass
from deepscout_evaluation.learning.models import (
    ImprovementCandidate,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
    LearningCase,
    LearningSubsystem,
    TrustLevel,
)

_POLICY_TEMPLATES: dict[str, dict] = {
    FailureClass.COVERAGE_FAILURE.value: {
        "candidate_type": ImprovementCandidateType.COVERAGE_POLICY,
        "policy_delta": {"gap_queries_per_round_bonus": 1},
        "title": "Increase bounded gap queries per corrective round",
        "expected_benefit": "More authoritative sources searched for critical gaps",
        "possible_regressions": "Higher tool-call cost per run",
        "requires_human": False,
    },
    FailureClass.RETRIEVAL_FAILURE.value: {
        "candidate_type": ImprovementCandidateType.RETRIEVAL_PARAMETER,
        "policy_delta": {"retrieval_candidate_k_multiplier": 1.1},
        "title": "Slightly widen retrieval candidate pool",
        "expected_benefit": "Recover missed relevant sources",
        "possible_regressions": "Latency and fusion noise",
        "requires_human": False,
    },
    FailureClass.PLANNING_FAILURE.value: {
        "candidate_type": ImprovementCandidateType.PLANNER_POLICY,
        "policy_delta": {"planner_decomposition_strictness": 0.65, "max_tasks_bonus": 1},
        "title": "Tighten planner decomposition for complex goals",
        "expected_benefit": "Better task coverage for multi-part questions",
        "possible_regressions": "Higher planning cost",
        "requires_human": True,
    },
    FailureClass.RUNTIME_FAILURE.value: {
        "candidate_type": ImprovementCandidateType.WORKER_POLICY,
        "policy_delta": {"allocation_parallel_preference": 0.35},
        "title": "Prefer sequential allocation to reduce duplicate work",
        "expected_benefit": "Lower duplicate tool calls",
        "possible_regressions": "Slower wall-clock on wide DAGs",
        "requires_human": True,
    },
    FailureClass.SYNTHESIS_FAILURE.value: {
        "candidate_type": ImprovementCandidateType.SYNTHESIS_POLICY,
        "policy_delta": {"report_rewrite_bonus": 1},
        "title": "Allow one additional bounded report rewrite",
        "expected_benefit": "Recover from revision-required critic verdicts",
        "possible_regressions": "Higher synthesis token cost",
        "requires_human": True,
    },
    FailureClass.COST_FAILURE.value: {
        "candidate_type": ImprovementCandidateType.CONFIGURATION,
        "policy_delta": {"prefer_lower_cost_strategy": True},
        "title": "Prefer lower-cost strategy when quality equivalent",
        "expected_benefit": "Reduce tool-call spend",
        "possible_regressions": "Coverage may decrease",
        "requires_human": False,
    },
    FailureClass.OPPORTUNITY.value: {
        "candidate_type": ImprovementCandidateType.CONFIGURATION,
        "policy_delta": {"prefer_lower_cost_strategy": True},
        "title": "Prefer lower-cost strategy when quality equivalent",
        "expected_benefit": "Reduce cost without quality loss",
        "possible_regressions": "Premature optimization on small samples",
        "requires_human": False,
    },
}


def generate_improvement_candidate(case: LearningCase) -> ImprovementCandidate | None:
    """Create a typed improvement candidate from a diagnosed case."""
    root = case.root_cause_class or case.failure_class
    template = _POLICY_TEMPLATES.get(root)
    if template is None:
        return ImprovementCandidate(
            learning_case_id=case.case_id,
            candidate_type=ImprovementCandidateType.CODE_PROPOSAL,
            title=f"Engineering fix for {root}",
            rationale=f"Observed: {case.symptom}",
            affected_subsystem=case.subsystem,
            policy_delta={},
            expected_benefit="Address root cause via code change",
            possible_regressions="Unknown without targeted regression",
            evaluation_plan={"regression_gate": True, "human_review": True},
            supporting_case_ids=[case.case_id],
            trust_level=TrustLevel.SANITIZED_CANDIDATE,
            status=ImprovementCandidateStatus.REQUIRES_HUMAN_REVIEW,
            owner_principal_id=case.owner_principal_id,
            confidence=case.confidence,
            rollback_info={"action": "no_runtime_change"},
        )

    return ImprovementCandidate(
        learning_case_id=case.case_id,
        candidate_type=template["candidate_type"],
        title=template["title"],
        rationale=f"Root cause {root}: {case.symptom}",
        policy_delta=dict(template["policy_delta"]),
        expected_benefit=template["expected_benefit"],
        possible_regressions=template["possible_regressions"],
        affected_subsystem=case.subsystem
        if case.subsystem != LearningSubsystem.EVALUATION
        else LearningSubsystem.COVERAGE,
        evaluation_plan={
            "regression_gate": True,
            "learning_loop_fixture": True,
            "requires_human": template.get("requires_human", True),
        },
        supporting_case_ids=[case.case_id],
        trust_level=TrustLevel.SANITIZED_CANDIDATE,
        status=ImprovementCandidateStatus.DRAFT,
        owner_principal_id=case.owner_principal_id,
        confidence=case.confidence,
        rollback_info={"revert_policy_delta": {}},
    )
