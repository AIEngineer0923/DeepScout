"""Background worker process for durable research jobs."""

from __future__ import annotations

import logging
import socket
import time
import uuid

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.jobs.service import JobService
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider

logger = logging.getLogger(__name__)


def _owner_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


def run_worker(*, poll_interval_s: float = 2.0, once: bool = False) -> None:
    settings = get_settings()
    configure = __import__(
        "deepscout_api.main", fromlist=["configure_observability"]
    ).configure_observability
    configure(settings)
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
            dispatch_due_monitors(store, settings, owner=owner)
            store.commit()
        except Exception:
            session.rollback()
            logger.exception("Monitor dispatch failed")
        job = jobs.claim_next(owner)
        if job is None:
            session.close()
            if once:
                return
            time.sleep(poll_interval_s)
            continue
        try:
            from deepscout_research.credentials.runtime import resolve_run_settings

            run_settings = resolve_run_settings(store, settings, job.research_run_id)
            with TavilyWebSearchProvider(run_settings) as search:
                orchestrator = ResearchOrchestrator(store, run_settings, search)
                orchestrator.execute(job.research_run_id)
            session.commit()
            jobs.complete(job.id, owner, job.lease_token or "")
        except Exception as exc:
            session.rollback()
            logger.exception("Job failed", extra={"job_id": str(job.id)})
            session = session_factory()
            store = ResearchStore(session)
            jobs = JobService(store)
            jobs.fail(job.id, owner, job.lease_token or "", str(exc))
            session.commit()
        finally:
            session.close()
        if once:
            return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
