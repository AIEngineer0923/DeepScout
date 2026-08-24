"""Canonical bounded semantics for Quick, Standard, and Deep research modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from deepscout_core.domain.budget import ResearchBudget

ResearchModeName = Literal["quick", "standard", "deep"]


@dataclass(frozen=True, slots=True)
class ResearchModeProfile:
    mode: ResearchModeName
    max_requirement_tasks: int
    search_results_per_query: int
    max_coverage_rounds: int
    gap_queries_per_round: int
    report_rewrites: int
    max_index_tokens: int


_PROFILES: dict[ResearchModeName, ResearchModeProfile] = {
    "quick": ResearchModeProfile("quick", 1, 2, 1, 1, 1, 10_000),
    "standard": ResearchModeProfile("standard", 9, 5, 2, 3, 2, 50_000),
    "deep": ResearchModeProfile("deep", 12, 8, 3, 3, 3, 100_000),
}


def normalize_research_mode(mode: str | None) -> ResearchModeName:
    return mode if mode in _PROFILES else "standard"  # type: ignore[return-value]


def research_profile(mode: str | None) -> ResearchModeProfile:
    return _PROFILES[normalize_research_mode(mode)]


def budget_for_research_mode(budget: ResearchBudget, mode: str | None) -> ResearchBudget:
    normalized = normalize_research_mode(mode)
    if normalized == "quick":
        return ResearchBudget(
            max_iterations=min(2, budget.max_iterations),
            max_wall_time_seconds=min(300, budget.max_wall_time_seconds),
            max_total_tokens=min(40_000, budget.max_total_tokens),
            max_cost_usd=min(1.0, budget.max_cost_usd),
            max_sources=min(8, budget.max_sources),
            max_tool_calls=min(16, budget.max_tool_calls),
        )
    if normalized == "deep":
        return ResearchBudget(
            max_iterations=max(8, budget.max_iterations),
            max_wall_time_seconds=max(budget.max_wall_time_seconds, 1200),
            max_total_tokens=max(budget.max_total_tokens, 400_000),
            max_cost_usd=max(budget.max_cost_usd, 8.0),
            max_sources=max(budget.max_sources, 60),
            max_tool_calls=max(budget.max_tool_calls, 120),
        )
    return budget
