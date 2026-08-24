"""Deterministic research termination policy."""

from dataclasses import dataclass

from deepscout_core.domain.budget import BudgetConsumption, ResearchBudget
from deepscout_core.domain.enums import (
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
)
from deepscout_core.domain.schemas import ResearchQuestionRead, ResearchTaskRead

from deepscout_research.tasks.graph import TaskGraph


@dataclass(frozen=True, slots=True)
class TerminationDecision:
    should_stop: bool
    reason: str
    terminal_status: ResearchRunStatus = ResearchRunStatus.COMPLETED


def evaluate_termination(
    *,
    budget: ResearchBudget,
    consumption: BudgetConsumption,
    questions: list[ResearchQuestionRead],
    tasks: list[ResearchTaskRead] | None = None,
) -> TerminationDecision:
    if tasks:
        graph = TaskGraph(tuple(tasks))
        if graph.all_terminal():
            completed = any(task.status == ResearchTaskStatus.COMPLETED for task in tasks)
            unsuccessful = any(
                task.status in {ResearchTaskStatus.BLOCKED, ResearchTaskStatus.FAILED}
                for task in tasks
            )
            if unsuccessful and not completed:
                return TerminationDecision(
                    should_stop=True,
                    reason="no_research_task_made_progress",
                    terminal_status=ResearchRunStatus.FAILED,
                )
            return TerminationDecision(
                should_stop=True,
                reason="no_active_tasks",
                terminal_status=ResearchRunStatus.COMPLETED,
            )
    if consumption.is_exhausted(budget):
        return TerminationDecision(
            should_stop=True,
            reason="budget_exhausted",
            terminal_status=ResearchRunStatus.BUDGET_EXHAUSTED,
        )
    if consumption.iterations >= budget.max_iterations:
        return TerminationDecision(
            should_stop=True,
            reason="max_iterations",
            terminal_status=ResearchRunStatus.COMPLETED,
        )

    if tasks:
        ready = graph.ready_tasks()
        if not ready and not any(
            task.status.value in {"pending", "ready", "running"} for task in tasks
        ):
            return TerminationDecision(
                should_stop=True,
                reason="no_active_tasks",
                terminal_status=ResearchRunStatus.COMPLETED,
            )
        return TerminationDecision(should_stop=False, reason="continue")

    active = [
        question
        for question in questions
        if question.status in {ResearchQuestionStatus.PENDING, ResearchQuestionStatus.RESEARCHING}
    ]
    if not active:
        return TerminationDecision(
            should_stop=True,
            reason="no_active_questions",
            terminal_status=ResearchRunStatus.COMPLETED,
        )

    return TerminationDecision(should_stop=False, reason="continue")
