"""Research monitor dispatch — durable Postgres leases, no extra broker."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from deepscout_core.domain.enums import RunLineageKind
from deepscout_core.domain.schemas import ResearchMonitorCreate, ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.models import ResearchMonitorRow
from deepscout_persistence.store import ResearchStore

from deepscout_research.jobs.service import JobService
from deepscout_research.monitors.schedule import catch_up_next_run, compute_next_run_at

MAX_MONITORS = 25
LEASE_SECONDS = 60


def monitor_status(row: ResearchMonitorRow, *, child_running: bool = False) -> str:
    if not row.enabled:
        return "disabled"
    if child_running:
        return "running"
    return "active"


def create_monitor(
    store: ResearchStore, payload: ResearchMonitorCreate, *, owner_principal_id=None
) -> ResearchMonitorRow:
    if store.count_monitors() >= MAX_MONITORS:
        raise ValueError("MODE A monitor limit reached")
    now = datetime.now(UTC)
    row = store.create_monitor(
        payload,
        next_run_at=compute_next_run_at(payload, after=now),
        owner_principal_id=owner_principal_id,
    )
    return row


def dispatch_due_monitors(
    store: ResearchStore,
    settings: Settings,
    *,
    owner: str,
    now: datetime | None = None,
) -> list[uuid.UUID]:
    now = now or datetime.now(UTC)
    claimed = store.claim_due_monitors(owner, now=now, lease_seconds=LEASE_SECONDS)
    started: list[uuid.UUID] = []
    jobs = JobService(store)
    for row in claimed:
        try:
            if store.monitor_has_active_run(row.id):
                store.release_monitor_lease(row.id, next_run_at=row.next_run_at or now)
                continue
            mode = (
                row.research_mode
                if row.research_mode in {"quick", "standard", "deep"}
                else "standard"
            )
            created = store.create_run(
                ResearchRunCreate(goal=row.goal, research_mode=mode),
                settings,
                parent_run_id=row.last_run_id,
                fork_reason="monitor",
                root_run_id=row.last_run_id,
                monitor_id=row.id,
                lineage_kind=RunLineageKind.MONITOR.value,
                owner_principal_id=row.owner_principal_id,
            )
            jobs.enqueue_execute_run(created.id)
            nxt = catch_up_next_run(row, now=now)
            store.complete_monitor_dispatch(row.id, run_id=created.id, next_run_at=nxt, now=now)
            started.append(created.id)
        except Exception:
            store.fail_monitor_dispatch(row.id, next_run_at=now + timedelta(minutes=15))
    return started
