"""Budget gate — deterministic checks before tool/iteration work."""

from datetime import UTC, datetime
from uuid import UUID

from deepscout_core.domain.budget import (
    BudgetExhaustedError,
    BudgetMetric,
    WallTimeBudgetExhaustedError,
)
from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.store import ResearchStore


class BudgetGate:
    def __init__(self, store: ResearchStore) -> None:
        self._store = store

    def reserve_tool_call(self, run_id: UUID, *, note: str = "") -> ResearchRunRow:
        self.ensure_wall_time_available(run_id)
        return self._store.record_budget_usage(
            run_id,
            BudgetMetric.TOOL_CALLS,
            1,
            note=note or "tool_call",
        )

    def reserve_iteration(self, run_id: UUID, *, note: str = "") -> ResearchRunRow:
        self.ensure_wall_time_available(run_id)
        return self._store.record_budget_usage(
            run_id,
            BudgetMetric.ITERATIONS,
            1,
            note=note or "research_iteration",
        )

    def reserve_source(self, run_id: UUID, *, note: str = "") -> ResearchRunRow:
        self.ensure_wall_time_available(run_id)
        return self._store.record_budget_usage(
            run_id,
            BudgetMetric.SOURCES,
            1,
            note=note or "source_discovered",
        )

    def ensure_tool_budget_available(self, row: ResearchRunRow) -> None:
        if row.consumed_tool_calls >= row.max_tool_calls:
            raise BudgetExhaustedError("Tool call budget exhausted")

    def ensure_wall_time_available(self, run_id: UUID) -> None:
        row = self._store.get_run_row(run_id)
        if row is None:
            raise LookupError(f"ResearchRun {run_id} not found")
        started_at = row.started_at or row.created_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        elapsed = (datetime.now(UTC) - started_at).total_seconds()
        if elapsed >= row.max_wall_time_seconds:
            raise WallTimeBudgetExhaustedError("Wall-time budget exhausted")
