"""Regression for durable worker completion transaction ordering."""

from __future__ import annotations

from deepscout_research.jobs.worker import _persist_job_completion


def test_job_completion_is_committed_after_lease_completion() -> None:
    calls: list[tuple] = []

    class Jobs:
        def complete(self, job_id, owner, lease_token) -> None:
            calls.append(("complete", job_id, owner, lease_token))

    class Session:
        def commit(self) -> None:
            calls.append(("commit",))

    _persist_job_completion(Jobs(), Session(), "job-1", "worker-1", "lease-1")  # type: ignore[arg-type]
    assert calls == [
        ("complete", "job-1", "worker-1", "lease-1"),
        ("commit",),
    ]
