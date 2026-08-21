from datetime import UTC, datetime, timedelta

import pytest
from deepscout_core.domain.enums import ResearchJobStatus, ResearchJobType
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import get_settings


@pytest.fixture
def settings():
    return get_settings()


@pytest.mark.postgres
def test_stale_job_lease_is_reclaimable(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Job lease", budget=settings.default_research_budget()),
        settings,
    )
    job = store.enqueue_job(
        run.id,
        job_type=ResearchJobType.EXECUTE_RUN,
        idempotency_key=f"lease-test-{run.id}",
    )
    claimed_a = store.claim_next_job("worker-a", lease_seconds=1, job_id=job.id)
    assert claimed_a is not None
    assert claimed_a.id == job.id
    token_a = claimed_a.lease_token
    claimed_a.lease_expires_at = datetime.now(UTC) - timedelta(seconds=5)
    store._session.flush()

    claimed_b = store.claim_next_job("worker-b", lease_seconds=30, job_id=job.id)
    assert claimed_b is not None
    assert claimed_b.id == job.id
    assert claimed_b.lease_owner == "worker-b"

    with pytest.raises(LookupError):
        store.complete_job(job.id, owner="worker-a", lease_token=token_a)

    store.complete_job(job.id, owner="worker-b", lease_token=claimed_b.lease_token)
    store._session.flush()
    from deepscout_persistence.models import ResearchJobRow

    row = store._session.get(ResearchJobRow, job.id)
    assert row is not None
    assert row.status == ResearchJobStatus.COMPLETED
