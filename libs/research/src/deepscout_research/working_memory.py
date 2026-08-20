"""Bounded working memory for an active research run or worker."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from deepscout_core.domain.schemas import ResearchQuestionRead, SearchResult


@dataclass
class WorkingMemory:
    run_id: UUID
    task_id: UUID | None = None
    iteration: int = 0
    scratch: dict[str, str] = field(default_factory=dict)
    recent_tool_summaries: list[str] = field(default_factory=list)
    active_questions: list[ResearchQuestionRead] = field(default_factory=list)
    latest_search_results: list[SearchResult] = field(default_factory=list)
    max_recent_summaries: int = 8

    def remember(self, key: str, value: str) -> None:
        self.scratch[key] = value[:4000]

    def remember_tool_summary(self, summary: str) -> None:
        self.recent_tool_summaries.append(summary[:2000])
        if len(self.recent_tool_summaries) > self.max_recent_summaries:
            self.recent_tool_summaries = self.recent_tool_summaries[-self.max_recent_summaries :]

    def snapshot(self) -> dict[str, object]:
        return {
            "run_id": str(self.run_id),
            "task_id": str(self.task_id) if self.task_id else None,
            "iteration": self.iteration,
            "scratch": dict(self.scratch),
            "recent_tool_summaries": list(self.recent_tool_summaries),
        }
