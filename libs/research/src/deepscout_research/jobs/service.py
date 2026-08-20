"""PostgreSQL-backed durable research job queue."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from deepscout_core.domain.enums import ResearchJobType
from deepscout_persistence.models import ResearchJobRow
from deepscout_persistence.store import ResearchStore


class JobService:
    def __init__(self, store: ResearchStore, *, lease_seconds: int = 120) -> None:
        self._store = store
        self._lease_seconds = lease_seconds

    def enqueue_execute_run(self, run_id: uuid.UUID) -> ResearchJobRow:
        return self._store.enqueue_job(
            run_id,
            job_type=ResearchJobType.EXECUTE_RUN,
            idempotency_key=f"execute:{run_id}",
        )

    def enqueue_resume_run(self, run_id: uuid.UUID) -> ResearchJobRow:
        return self._store.enqueue_job(
            run_id,
            job_type=ResearchJobType.RESUME_RUN,
            idempotency_key=f"resume:{run_id}:{uuid.uuid4()}",
        )

    def claim_next(self, owner: str) -> ResearchJobRow | None:
        return self._store.claim_next_job(owner, lease_seconds=self._lease_seconds)

    def heartbeat(self, job_id: uuid.UUID, owner: str, lease_token: str) -> None:
        self._store.renew_job_lease(
            job_id, owner=owner, lease_token=lease_token, lease_seconds=self._lease_seconds
        )

    def complete(self, job_id: uuid.UUID, owner: str, lease_token: str) -> None:
        self._store.complete_job(job_id, owner=owner, lease_token=lease_token)

    def fail(
        self, job_id: uuid.UUID, owner: str, lease_token: str, error: str, *, retry: bool = True
    ) -> None:
        self._store.fail_job(
            job_id,
            owner=owner,
            lease_token=lease_token,
            error=error,
            retry=retry,
        )

    def recover_stale(self) -> int:
        return self._store.recover_stale_jobs(datetime.now(UTC))
