"""Domain invariant violations."""

from uuid import UUID

from deepscout_core.domain.enums import (
    TERMINAL_RESEARCH_QUESTION_STATUSES,
    TERMINAL_RESEARCH_RUN_STATUSES,
    VERIFIED_CLAIM_STATUSES,
    ClaimVerificationStatus,
    ContradictionEvidenceStatus,
    ResearchQuestionStatus,
    ResearchRunStatus,
)


class DomainInvariantError(ValueError):
    """Raised when a domain rule is violated."""


def assert_claim_verification_allowed(
    *,
    verification_status: ClaimVerificationStatus,
    evidence_count: int,
) -> None:
    if verification_status in VERIFIED_CLAIM_STATUSES and evidence_count == 0:
        raise DomainInvariantError("A claim cannot be verified without evidence")


def assert_evidence_has_snapshot(*, snapshot_id: object | None) -> None:
    if snapshot_id is None:
        raise DomainInvariantError("Evidence must reference a SourceSnapshot")


def assert_decision_claims_are_verified(
    *,
    claim_statuses: list[ClaimVerificationStatus],
) -> None:
    allowed = {
        ClaimVerificationStatus.VERIFIED,
        ClaimVerificationStatus.PARTIALLY_VERIFIED,
    }
    for status in claim_statuses:
        if status not in allowed:
            raise DomainInvariantError("Decision requires verified or partially verified claims")


def assert_run_status_transition(
    *,
    current: ResearchRunStatus,
    new: ResearchRunStatus,
) -> None:
    if current in TERMINAL_RESEARCH_RUN_STATUSES and new == ResearchRunStatus.RUNNING:
        raise DomainInvariantError("Terminal research runs cannot be restarted implicitly")


def assert_question_status_transition(
    *,
    current: ResearchQuestionStatus,
    new: ResearchQuestionStatus,
) -> None:
    if current in TERMINAL_RESEARCH_QUESTION_STATUSES and new in {
        ResearchQuestionStatus.PENDING,
        ResearchQuestionStatus.RESEARCHING,
    }:
        raise DomainInvariantError("Terminal research questions cannot revert to active states")


def assert_report_has_evidence(*, evidence_ids: list[object]) -> None:
    if not evidence_ids:
        raise DomainInvariantError("Report must reference evidence used in synthesis")


def assert_contradiction_invariants(
    *,
    claim_a_id: UUID,
    claim_b_id: UUID,
    claim_a_run_id: UUID,
    claim_b_run_id: UUID,
    run_id: UUID,
    evidence_status: ContradictionEvidenceStatus,
    claim_a_evidence_count: int,
    claim_b_evidence_count: int,
) -> None:
    if claim_a_id == claim_b_id:
        raise DomainInvariantError("Contradiction must link two distinct claims")
    if claim_a_run_id != run_id or claim_b_run_id != run_id:
        raise DomainInvariantError("Contradiction claims must belong to the same research run")
    if evidence_status == ContradictionEvidenceStatus.SUFFICIENT and (
        claim_a_evidence_count == 0 or claim_b_evidence_count == 0
    ):
        raise DomainInvariantError(
            "Contradiction marked sufficient requires evidence on both claims"
        )


def assert_same_run(*, expected_run_id: UUID, actual_run_id: UUID, entity: str) -> None:
    if expected_run_id != actual_run_id:
        raise DomainInvariantError(f"{entity} must belong to research run {expected_run_id}")


def assert_snapshot_immutable(*, existing_hash: str, new_hash: str) -> None:
    if existing_hash != new_hash:
        raise DomainInvariantError("SourceSnapshot content is immutable; create a new snapshot")
