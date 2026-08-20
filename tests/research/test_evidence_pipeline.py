import pytest
from deepscout_core.domain.schemas import (
    ResearchPlanWrite,
    ResearchRunCreate,
    SearchCandidateWrite,
    SearchResult,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_research.phases.extract import extract_claims_for_run
from deepscout_research.phases.verify import verify_claims_for_run


@pytest.mark.postgres
def test_extract_and_verify_claims_from_snapshot(store, settings) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Battery chemistries", budget=settings.default_research_budget()),
        settings,
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(strategy="s", success_criteria="c", questions=["What is NMC?"]),
    )
    question = store.list_questions(run.id)[0]
    source, _ = store.add_source(
        run.id,
        SourceWrite(canonical_url="https://example.com/nmc", title="NMC", domain="example.com"),
    )
    snippet = "NMC batteries offer higher energy density than LFP chemistry."
    store.add_search_candidates(
        run.id,
        SearchCandidateWrite(
            query="What is NMC?",
            provider="fake",
            results=[SearchResult(url=source.canonical_url, title="NMC", snippet=snippet)],
            question_id=question.id,
        ),
    )
    store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content=f"Intro. {snippet} End.", mime_type="text/plain"),
    )

    stats = extract_claims_for_run(store, run.id)
    assert stats["claims_created"] == 1
    assert stats["evidence_created"] == 1

    verify_stats = verify_claims_for_run(store, run.id)
    assert verify_stats["verified"] == 1
    claims = store.list_claims(run.id)
    assert len(claims) == 1
    assert claims[0].verification_status.value == "verified"
