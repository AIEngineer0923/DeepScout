"""Typed application events for research runs (SSE foundation)."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from deepscout_core.domain.enums import ResearchPhase


class ResearchEventType(StrEnum):
    RUN_STARTED = "run.started"
    PHASE_STARTED = "phase.started"
    PHASE_COMPLETED = "phase.completed"
    SOURCE_DISCOVERED = "source.discovered"
    BUDGET_UPDATED = "budget.updated"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


class ResearchEvent(BaseModel):
    event_type: ResearchEventType
    run_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase: ResearchPhase | None = None
    iteration: int | None = None
    payload: dict[str, str | int | float] = Field(default_factory=dict)
