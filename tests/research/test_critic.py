import pytest
from deepscout_core.domain.schemas import ClaimWrite, ResearchRunCreate, SourceWrite
from deepscout_research.phases.critic import run_critic_for_run


@pytest.mark.postgres
def test_critic_passes_when_no_claims(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Test critic skip", budget=settings.default_research_budget()),
        settings,
    )
    store.commit()
    result = run_critic_for_run(store, run.id)
    assert result.passed is True
    assert result.issues == []


@pytest.mark.postgres
def test_critic_flags_claim_without_evidence(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Test critic fail", budget=settings.default_research_budget()),
        settings,
    )
    source, _ = store.add_source(
        run.id,
        SourceWrite(canonical_url="https://example.com/a", title="Example", domain="example.com"),
    )
    store.add_claim(
        run.id,
        ClaimWrite(source_id=source.id, statement="Battery density is high."),
    )
    store.commit()
    result = run_critic_for_run(store, run.id)
    assert result.passed is False
    assert any("lack evidence" in issue for issue in result.issues)
