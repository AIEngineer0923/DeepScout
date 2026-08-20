"""Budget gate — deterministic checks before tool/iteration work."""

from uuid import UUID

from deepscout_core.domain.budget import BudgetExhaustedError, BudgetMetric
from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.store import ResearchStore


class BudgetGate:
    def __init__(self, store: ResearchStore) -> None:
        self._store = store

    def reserve_tool_call(self, run_id: UUID, *, note: str = "") -> ResearchRunRow:
        return self._store.record_budget_usage(
            run_id,
            BudgetMetric.TOOL_CALLS,
            1,
            note=note or "tool_call",
        )

    def reserve_iteration(self, run_id: UUID, *, note: str = "") -> ResearchRunRow:
        return self._store.record_budget_usage(
            run_id,
            BudgetMetric.ITERATIONS,
            1,
            note=note or "research_iteration",
        )

    def reserve_source(self, run_id: UUID, *, note: str = "") -> ResearchRunRow:
        return self._store.record_budget_usage(
            run_id,
            BudgetMetric.SOURCES,
            1,
            note=note or "source_discovered",
        )

    def ensure_tool_budget_available(self, row: ResearchRunRow) -> None:
        if row.consumed_tool_calls >= row.max_tool_calls:
            raise BudgetExhaustedError("Tool call budget exhausted")
