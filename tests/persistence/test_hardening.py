import pytest
from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.enums import (
    BudgetMetric,
    ContradictionEvidenceStatus,
    ResearchQuestionStatus,
)
from deepscout_core.domain.invariants import DomainInvariantError
from deepscout_core.domain.schemas import (
    ClaimWrite,
    ContradictionWrite,
    EvidenceWrite,
    ResearchPlanWrite,
    ResearchRunCreate,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_persistence.models import ResearchRunRow


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)


def test_snapshot_refetch_creates_new_row(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Immutability"), settings)
    source, _ = store.add_source(run.id, SourceWrite(canonical_url="https://example.com/x"))
    first = store.add_snapshot(source.id, SourceSnapshotWrite(content="version-one"))
    second = store.add_snapshot(source.id, SourceSnapshotWrite(content="version-two"))
    assert first.id != second.id
    assert first.content_hash != second.content_hash


def test_cross_run_evidence_rejected(store, settings) -> None:
    run_a = store.create_run(ResearchRunCreate(goal="Run A"), settings)
    run_b = store.create_run(ResearchRunCreate(goal="Run B"), settings)
    source_b, _ = store.add_source(run_b.id, SourceWrite(canonical_url="https://example.com/b"))
    snapshot_b = store.add_snapshot(source_b.id, SourceSnapshotWrite(content="B content"))
    claim_a = store.add_claim(run_a.id, ClaimWrite(statement="Claim in A"))
    with pytest.raises(DomainInvariantError):
        store.attach_evidence(
            claim_a.id,
            EvidenceWrite(snapshot_id=snapshot_b.id, quote="cross run"),
        )


def test_contradiction_rejects_same_claim(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Contradiction"), settings)
    claim = store.add_claim(run.id, ClaimWrite(statement="Only one"))
    with pytest.raises(DomainInvariantError):
        store.add_contradiction(
            run.id,
            ContradictionWrite(
                claim_a_id=claim.id,
                claim_b_id=claim.id,
                description="invalid",
                evidence_status=ContradictionEvidenceStatus.INSUFFICIENT_EVIDENCE,
            ),
        )


def test_contradiction_duplicate_pair_is_idempotent(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Dup contradiction"), settings)
    claim_a = store.add_claim(run.id, ClaimWrite(statement="A"))
    claim_b = store.add_claim(run.id, ClaimWrite(statement="B"))
    payload = ContradictionWrite(
        claim_a_id=claim_a.id,
        claim_b_id=claim_b.id,
        description="conflict",
        evidence_status=ContradictionEvidenceStatus.INSUFFICIENT_EVIDENCE,
    )
    first = store.add_contradiction(run.id, payload)
    second = store.add_contradiction(
        run.id,
        ContradictionWrite(
            claim_a_id=claim_b.id,
            claim_b_id=claim_a.id,
            description="conflict",
            evidence_status=ContradictionEvidenceStatus.INSUFFICIENT_EVIDENCE,
        ),
    )
    assert first.id == second.id


def test_question_terminal_state_cannot_revert(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Question lifecycle"), settings)
    store.save_plan(
        run.id,
        ResearchPlanWrite(strategy="s", success_criteria="c", questions=["Q1"]),
    )
    question = store.list_questions(run.id)[0]
    store.update_question_status(question.id, ResearchQuestionStatus.ANSWERED)
    with pytest.raises(DomainInvariantError):
        store.update_question_status(question.id, ResearchQuestionStatus.PENDING)


def test_budget_sequential_increments(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Atomic budget", budget=ResearchBudget(max_tool_calls=2)),
        settings,
    )
    store.record_budget_usage(run.id, BudgetMetric.TOOL_CALLS, 1)
    store.record_budget_usage(run.id, BudgetMetric.TOOL_CALLS, 1)
    row = db_session.get(ResearchRunRow, run.id)
    assert row is not None
    assert row.consumed_tool_calls == 2
