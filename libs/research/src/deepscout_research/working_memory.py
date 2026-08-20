"""Bounded working memory for an active research run."""

from dataclasses import dataclass, field
from uuid import UUID

from deepscout_core.domain.schemas import ResearchQuestionRead, SearchResult


@dataclass
class WorkingMemory:
    run_id: UUID
    iteration: int = 0
    recent_tool_summaries: list[str] = field(default_factory=list)
    active_questions: list[ResearchQuestionRead] = field(default_factory=list)
    latest_search_results: list[SearchResult] = field(default_factory=list)
    max_recent_summaries: int = 8

    def remember_tool_summary(self, summary: str) -> None:
        self.recent_tool_summaries.append(summary[:2000])
        if len(self.recent_tool_summaries) > self.max_recent_summaries:
            self.recent_tool_summaries = self.recent_tool_summaries[-self.max_recent_summaries :]
