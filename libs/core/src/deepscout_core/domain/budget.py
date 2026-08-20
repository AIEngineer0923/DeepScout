"""Research budget limits and deterministic ledger."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from deepscout_core.domain.enums import BudgetMetric


@dataclass(frozen=True, slots=True)
class ResearchBudget:
    """Configurable limits for a single research run."""

    max_iterations: int = 5
    max_wall_time_seconds: int = 900
    max_total_tokens: int = 200_000
    max_cost_usd: float = 5.0
    max_sources: int = 40
    max_tool_calls: int = 80

    def __post_init__(self) -> None:
        for name in (
            "max_iterations",
            "max_wall_time_seconds",
            "max_total_tokens",
            "max_sources",
            "max_tool_calls",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")


@dataclass(frozen=True, slots=True)
class BudgetConsumption:
    iterations: int = 0
    wall_time_seconds: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    sources: int = 0
    tool_calls: int = 0

    def remaining(self, budget: ResearchBudget) -> dict[BudgetMetric, float | int]:
        return {
            BudgetMetric.ITERATIONS: budget.max_iterations - self.iterations,
            BudgetMetric.WALL_TIME: budget.max_wall_time_seconds - self.wall_time_seconds,
            BudgetMetric.TOKENS: budget.max_total_tokens - self.total_tokens,
            BudgetMetric.COST: budget.max_cost_usd - self.cost_usd,
            BudgetMetric.SOURCES: budget.max_sources - self.sources,
            BudgetMetric.TOOL_CALLS: budget.max_tool_calls - self.tool_calls,
        }

    def is_exhausted(self, budget: ResearchBudget) -> bool:
        return (
            self.iterations >= budget.max_iterations
            or self.wall_time_seconds >= budget.max_wall_time_seconds
            or self.total_tokens >= budget.max_total_tokens
            or self.cost_usd >= budget.max_cost_usd
            or self.sources >= budget.max_sources
            or self.tool_calls >= budget.max_tool_calls
        )

    def would_exceed(self, budget: ResearchBudget, metric: BudgetMetric, delta: float) -> bool:
        updated = BudgetConsumption(
            iterations=self.iterations + int(delta)
            if metric == BudgetMetric.ITERATIONS
            else self.iterations,
            wall_time_seconds=self.wall_time_seconds + int(delta)
            if metric == BudgetMetric.WALL_TIME
            else self.wall_time_seconds,
            total_tokens=self.total_tokens + int(delta)
            if metric == BudgetMetric.TOKENS
            else self.total_tokens,
            cost_usd=self.cost_usd + delta if metric == BudgetMetric.COST else self.cost_usd,
            sources=self.sources + int(delta) if metric == BudgetMetric.SOURCES else self.sources,
            tool_calls=self.tool_calls + int(delta)
            if metric == BudgetMetric.TOOL_CALLS
            else self.tool_calls,
        )
        return (
            updated.iterations > budget.max_iterations
            or updated.wall_time_seconds > budget.max_wall_time_seconds
            or updated.total_tokens > budget.max_total_tokens
            or updated.cost_usd > budget.max_cost_usd
            or updated.sources > budget.max_sources
            or updated.tool_calls > budget.max_tool_calls
        )


@dataclass(frozen=True, slots=True)
class BudgetLedgerEntry:
    metric: BudgetMetric
    delta: float
    recorded_at: datetime
    note: str = ""


@dataclass
class BudgetLedger:
    """Append-only consumption log with deterministic enforcement."""

    budget: ResearchBudget
    consumption: BudgetConsumption = field(default_factory=BudgetConsumption)
    entries: list[BudgetLedgerEntry] = field(default_factory=list)

    def record(self, metric: BudgetMetric, delta: float, *, note: str = "") -> BudgetConsumption:
        if delta < 0:
            raise ValueError("Budget ledger cannot record negative deltas")

        updated = BudgetConsumption(
            iterations=self.consumption.iterations
            + (int(delta) if metric == BudgetMetric.ITERATIONS else 0),
            wall_time_seconds=self.consumption.wall_time_seconds
            + (int(delta) if metric == BudgetMetric.WALL_TIME else 0),
            total_tokens=self.consumption.total_tokens
            + (int(delta) if metric == BudgetMetric.TOKENS else 0),
            cost_usd=self.consumption.cost_usd + (delta if metric == BudgetMetric.COST else 0.0),
            sources=self.consumption.sources
            + (int(delta) if metric == BudgetMetric.SOURCES else 0),
            tool_calls=self.consumption.tool_calls
            + (int(delta) if metric == BudgetMetric.TOOL_CALLS else 0),
        )
        if self.consumption.would_exceed(self.budget, metric, delta):
            raise BudgetExhaustedError(f"Budget exhausted after recording {metric.value}")

        self.consumption = updated
        self.entries.append(
            BudgetLedgerEntry(
                metric=metric,
                delta=delta,
                recorded_at=datetime.now(UTC),
                note=note,
            )
        )
        return updated


class BudgetExhaustedError(Exception):
    """Raised when a budget limit would be exceeded."""
