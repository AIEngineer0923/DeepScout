"""Typed application events for research runs (SSE foundation)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from deepscout_core.domain.enums import ResearchPhase


class ResearchEventType(StrEnum):
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    PHASE_STARTED = "phase.started"
    PHASE_COMPLETED = "phase.completed"
    TASK_READY = "task.ready"
    WORKER_STARTED = "worker.started"
    WORKER_PROGRESS = "worker.progress"
    WORKER_COMPLETED = "worker.completed"
    WORKER_FAILED = "worker.failed"
    SOURCE_DISCOVERED = "source.discovered"
    SOURCE_FETCHED = "source.fetched"
    CLAIM_CREATED = "claim.created"
    EVIDENCE_CREATED = "evidence.created"
    CONTRADICTION_DETECTED = "contradiction.detected"
    CRITIC_STARTED = "critic.started"
    CRITIC_COMPLETED = "critic.completed"
    REPORT_READY = "report.ready"
    BUDGET_UPDATED = "budget.updated"


class ResearchEvent(BaseModel):
    event_type: ResearchEventType
    run_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase: ResearchPhase | None = None
    iteration: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
