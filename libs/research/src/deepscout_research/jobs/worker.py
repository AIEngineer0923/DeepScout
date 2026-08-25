"""Background worker process for durable research jobs."""

from __future__ import annotations

import logging
import socket
import time
import uuid

from deepscout_core.domain.enums import TERMINAL_RESEARCH_RUN_STATUSES
from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.credentials.runtime import (
    configure_process_observability,
    resolve_run_settings,
    run_observability_environment,
)
from deepscout_research.jobs.service import JobService
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider
from deepscout_research.source_fabric.router import build_discovery_router

logger = logging.getLogger(__name__)


def _owner_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


def _persist_job_completion(
    jobs: JobService,
    session,
    job_id,
    owner: str,
    lease_token: str,
) -> None:
    """Completion and commit are one ordered operation; closing a session must not roll it back."""
    jobs.complete(job_id, owner, lease_token)
    session.commit()


def run_worker(*, poll_interval_s: float = 2.0, once: bool = False) -> None:
    settings = get_settings()
    configure_process_observability(settings)
    owner = _owner_id()
    session_factory = get_session_factory(settings.database_url)

    while True:
        session = session_factory()
        store = ResearchStore(session)
        jobs = JobService(store)
        recovered = jobs.recover_stale()
        if recovered:
            logger.info("Recovered stale jobs", extra={"count": recovered})
        from deepscout_research.monitors.service import dispatch_due_monitors

        try:
            from deepscout_evaluation.learning.monitoring import close_expired_monitoring_windows

            dispatch_due_monitors(store, settings, owner=owner)
            closed = close_expired_monitoring_windows(store)
            if closed:
                logger.info("Closed expired policy monitoring windows", extra={"count": closed})
            store.commit()
        except Exception:
            session.rollback()
            logger.exception("Monitor dispatch failed")
        job = jobs.claim_next(owner)
        if job is None:
            try:
                from deepscout_evaluation.learning.experiment_jobs import (
                    process_learning_experiment_jobs,
                )

                processed = process_learning_experiment_jobs(store, owner, limit=2)
                if processed:
                    store.commit()
            except Exception:
                session.rollback()
                logger.exception("Learning experiment dispatch failed")
            session.close()
            if once:
                return
            time.sleep(poll_interval_s)
            continue
        job_id = job.id
        run_id = job.research_run_id
        lease_token = job.lease_token or ""
        try:
            run = store.get_run(run_id)
            if run is None:
                raise LookupError(f"Research run not found: {run_id}")
            if run.status in TERMINAL_RESEARCH_RUN_STATUSES:
                _persist_job_completion(jobs, session, job_id, owner, lease_token)
                if once:
                    return
                continue
            jobs.heartbeat(
                job_id,
                owner,
                lease_token,
                lease_seconds=max(120, run.budget.max_wall_time_seconds + 300),
            )
            session.commit()
            run_settings = resolve_run_settings(store, settings, run_id)
            web_search = TavilyWebSearchProvider(run_settings)
            with run_observability_environment(run_settings):
                with build_discovery_router(run_settings, web_search) as search:
                    orchestrator = ResearchOrchestrator(store, run_settings, search)
                    orchestrator.execute(run_id)
            _persist_job_completion(jobs, session, job_id, owner, lease_token)
        except Exception as exc:
            session.rollback()
            logger.exception("Job failed", extra={"job_id": str(job_id)})
            session = session_factory()
            store = ResearchStore(session)
            jobs = JobService(store)
            try:
                jobs.fail(job_id, owner, lease_token, str(exc))
                session.commit()
            except LookupError:
                session.rollback()
                logger.warning(
                    "Job lease was lost before failure could be persisted",
                    extra={"job_id": str(job_id)},
                )
        finally:
            session.close()
        if once:
            return


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Deep Scout worker started")
    run_worker()


if __name__ == "__main__":
    main()
