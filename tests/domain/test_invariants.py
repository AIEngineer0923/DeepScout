import pytest
from deepscout_core.domain.budget import (
    BudgetExhaustedError,
    BudgetLedger,
    BudgetMetric,
    ResearchBudget,
)
from deepscout_core.domain.enums import ClaimVerificationStatus, ResearchRunStatus
from deepscout_core.domain.invariants import (
    DomainInvariantError,
    assert_claim_verification_allowed,
    assert_decision_claims_are_verified,
    assert_report_has_evidence,
    assert_run_status_transition,
    assert_snapshot_immutable,
)


def test_claim_cannot_be_verified_without_evidence() -> None:
    with pytest.raises(DomainInvariantError):
        assert_claim_verification_allowed(
            verification_status=ClaimVerificationStatus.VERIFIED,
            evidence_count=0,
        )


def test_partially_verified_also_requires_evidence() -> None:
    with pytest.raises(DomainInvariantError):
        assert_claim_verification_allowed(
            verification_status=ClaimVerificationStatus.PARTIALLY_VERIFIED,
            evidence_count=0,
        )


def test_terminal_run_cannot_restart_implicitly() -> None:
    with pytest.raises(DomainInvariantError):
        assert_run_status_transition(
            current=ResearchRunStatus.COMPLETED,
            new=ResearchRunStatus.RUNNING,
        )


def test_decision_requires_verified_claims() -> None:
    with pytest.raises(DomainInvariantError):
        assert_decision_claims_are_verified(
            claim_statuses=[ClaimVerificationStatus.PENDING],
        )


def test_report_requires_evidence_references() -> None:
    with pytest.raises(DomainInvariantError):
        assert_report_has_evidence(evidence_ids=[])


def test_snapshot_immutability_invariant() -> None:
    with pytest.raises(DomainInvariantError):
        assert_snapshot_immutable(existing_hash="abc", new_hash="def")


def test_budget_ledger_rejects_over_limit() -> None:
    ledger = BudgetLedger(budget=ResearchBudget(max_iterations=1))
    ledger.record(BudgetMetric.ITERATIONS, 1)
    with pytest.raises(BudgetExhaustedError):
        ledger.record(BudgetMetric.ITERATIONS, 1)
