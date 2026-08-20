import uuid

import pytest
from deepscout_core.domain.budget import BudgetExhaustedError, BudgetMetric, ResearchBudget
from deepscout_core.domain.enums import (
    ClaimVerificationStatus,
    ContradictionEvidenceStatus,
    ResearchRunStatus,
)
from deepscout_core.domain.invariants import DomainInvariantError
from deepscout_core.domain.schemas import (
    ClaimWrite,
    ContradictionWrite,
    DecisionWrite,
    EvidenceWrite,
    ReportWrite,
    ResearchPlanWrite,
    ResearchRunCreate,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_persistence.models import BudgetLedgerEntryRow, ResearchRunRow
from sqlalchemy import select


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)


def test_create_and_get_research_run(store, settings) -> None:
    created = store.create_run(ResearchRunCreate(goal="Evaluate battery tech"), settings)
    loaded = store.get_run(created.id)
    assert loaded is not None
    assert loaded.goal == "Evaluate battery tech"
    assert loaded.llm_model == "gemini-3.7-flash"
    assert loaded.status == ResearchRunStatus.PENDING


def test_save_plan_and_questions(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Plan test"), settings)
    plan_id = store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="Compare chemistries",
            success_criteria="At least three verified claims",
            questions=["Which chemistry leads?", "What is the cost delta?"],
        ),
    )
    assert plan_id is not None
    with pytest.raises(ValueError, match="already exists"):
        store.save_plan(run.id, ResearchPlanWrite(strategy="x", success_criteria="y"))


def test_snapshot_deduplication_and_versioning(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Snapshot test"), settings)
    source, _created = store.add_source(
        run.id,
        SourceWrite(canonical_url="https://example.com/report", title="Report"),
    )
    first = store.add_snapshot(source.id, SourceSnapshotWrite(content="<html>v1</html>"))
    second = store.add_snapshot(source.id, SourceSnapshotWrite(content="<html>v1</html>"))
    assert first.id == second.id
    changed = store.add_snapshot(source.id, SourceSnapshotWrite(content="<html>v2</html>"))
    assert changed.id != first.id


def test_claim_requires_evidence_before_verification(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Evidence test"), settings)
    source, _created = store.add_source(run.id, SourceWrite(canonical_url="https://example.com/a"))
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content="Battery density improved."),
    )
    claim = store.add_claim(
        run.id,
        ClaimWrite(statement="Density improved", source_id=source.id),
    )

    with pytest.raises(DomainInvariantError):
        store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)

    evidence = store.attach_evidence(
        claim.id,
        EvidenceWrite(snapshot_id=snapshot.id, quote="Battery density improved."),
    )
    updated = store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)
    assert updated.verification_status == ClaimVerificationStatus.VERIFIED
    assert evidence.snapshot_id == snapshot.id


def test_decision_and_report_require_verified_evidence(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Decision test"), settings)
    source, _created = store.add_source(run.id, SourceWrite(canonical_url="https://example.com/b"))
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content="Solid-state wins on safety."),
    )
    claim = store.add_claim(
        run.id,
        ClaimWrite(statement="Solid-state is safer", source_id=source.id),
    )
    evidence = store.attach_evidence(
        claim.id,
        EvidenceWrite(snapshot_id=snapshot.id, quote="Solid-state wins on safety."),
    )

    with pytest.raises(DomainInvariantError):
        store.save_decision(
            run.id,
            DecisionWrite(
                recommendation="Prefer solid-state",
                rationale="Safety evidence",
                confidence=0.8,
                supporting_claim_ids=[claim.id],
            ),
        )

    store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)
    store.save_decision(
        run.id,
        DecisionWrite(
            recommendation="Prefer solid-state",
            rationale="Safety evidence",
            confidence=0.8,
            supporting_claim_ids=[claim.id],
        ),
    )
    store.save_report(
        run.id,
        ReportWrite(
            title="Battery safety summary",
            body_markdown="Solid-state appears safer.",
            cited_evidence_ids=[evidence.id],
        ),
    )


def test_contradiction_links_two_claims(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Contradiction test"), settings)
    claim_a = store.add_claim(run.id, ClaimWrite(statement="Density up"))
    claim_b = store.add_claim(run.id, ClaimWrite(statement="Density flat"))
    contradiction = store.add_contradiction(
        run.id,
        ContradictionWrite(
            claim_a_id=claim_a.id,
            claim_b_id=claim_b.id,
            description="Conflicting density trends",
            evidence_status=ContradictionEvidenceStatus.INSUFFICIENT_EVIDENCE,
        ),
    )
    assert contradiction.claim_a_id == claim_a.id


def test_terminal_run_cannot_restart(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Terminal test"), settings)
    store.update_run_status(run.id, ResearchRunStatus.RUNNING)
    store.update_run_status(run.id, ResearchRunStatus.COMPLETED)
    with pytest.raises(DomainInvariantError):
        store.update_run_status(run.id, ResearchRunStatus.RUNNING)


def test_budget_ledger_persists_and_blocks_overrun(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Budget test", budget=ResearchBudget(max_sources=1)),
        settings,
    )
    store.record_budget_usage(run.id, BudgetMetric.SOURCES, 1)
    row = db_session.get(ResearchRunRow, run.id)
    assert row is not None
    assert row.consumed_sources == 1
    entries = db_session.scalars(
        select(BudgetLedgerEntryRow).where(BudgetLedgerEntryRow.research_run_id == run.id)
    ).all()
    assert len(entries) == 1
    with pytest.raises(BudgetExhaustedError):
        store.record_budget_usage(run.id, BudgetMetric.SOURCES, 1)


def test_duplicate_source_url_is_idempotent(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Source dedupe"), settings)
    payload = SourceWrite(canonical_url="https://example.com/unique")
    first, created_first = store.add_source(run.id, payload)
    second, created_second = store.add_source(run.id, payload)
    assert first.id == second.id
    assert created_first is True
    assert created_second is False


def test_unknown_run_raises_lookup(store, settings) -> None:
    with pytest.raises(LookupError):
        store.save_plan(
            uuid.uuid4(),
            ResearchPlanWrite(strategy="x", success_criteria="y", questions=["q"]),
        )
