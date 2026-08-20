from uuid import uuid4

import pytest
from deepscout_core.domain.budget import BudgetConsumption, ResearchBudget
from deepscout_core.domain.enums import ContradictionEvidenceStatus, ResearchQuestionStatus
from deepscout_core.domain.invariants import (
    DomainInvariantError,
    assert_contradiction_invariants,
    assert_question_status_transition,
)
from deepscout_core.domain.schemas import ResearchQuestionRead
from deepscout_research.termination import evaluate_termination


def test_question_terminal_cannot_revert() -> None:
    with pytest.raises(DomainInvariantError):
        assert_question_status_transition(
            current=ResearchQuestionStatus.ANSWERED,
            new=ResearchQuestionStatus.PENDING,
        )


def test_contradiction_requires_distinct_claims() -> None:
    claim_id = uuid4()
    run_id = uuid4()
    with pytest.raises(DomainInvariantError):
        assert_contradiction_invariants(
            claim_a_id=claim_id,
            claim_b_id=claim_id,
            claim_a_run_id=run_id,
            claim_b_run_id=run_id,
            run_id=run_id,
            evidence_status=ContradictionEvidenceStatus.INSUFFICIENT_EVIDENCE,
            claim_a_evidence_count=0,
            claim_b_evidence_count=0,
        )


def test_termination_stops_when_budget_exhausted() -> None:
    decision = evaluate_termination(
        budget=ResearchBudget(max_tool_calls=1),
        consumption=BudgetConsumption(tool_calls=1),
        questions=[
            ResearchQuestionRead(
                id=uuid4(),
                text="Q",
                status=ResearchQuestionStatus.PENDING,
                sort_order=0,
            )
        ],
    )
    assert decision.should_stop is True
    assert decision.reason == "budget_exhausted"
