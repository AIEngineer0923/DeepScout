"""Research task DAG — deterministic scheduling primitives."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from deepscout_core.domain.enums import TERMINAL_RESEARCH_TASK_STATUSES, ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerTask, ResearchTaskRead


class TaskGraphError(ValueError):
    """Invalid task graph."""


@dataclass(frozen=True, slots=True)
class TaskGraph:
    tasks: tuple[ResearchTaskRead, ...]

    def by_key(self) -> dict[str, ResearchTaskRead]:
        return {task.task_key: task for task in self.tasks}

    def validate_dependencies(self) -> None:
        keys = {task.task_key for task in self.tasks}
        for task in self.tasks:
            for dep in task.depends_on:
                if dep not in keys:
                    raise TaskGraphError(f"Unknown dependency {dep} for task {task.task_key}")
                if dep == task.task_key:
                    raise TaskGraphError(f"Self dependency on {task.task_key}")
        self._detect_cycles()

    def _detect_cycles(self) -> None:
        by_key = self.by_key()
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visiting:
                raise TaskGraphError(f"Cycle detected at task {key}")
            if key in visited:
                return
            visiting.add(key)
            for dep in by_key[key].depends_on:
                visit(dep)
            visiting.remove(key)
            visited.add(key)

        for key in by_key:
            visit(key)

    def ready_tasks(self) -> list[ResearchTaskRead]:
        by_key = self.by_key()
        ready: list[ResearchTaskRead] = []
        for task in self.tasks:
            if task.status not in {ResearchTaskStatus.PENDING, ResearchTaskStatus.READY}:
                continue
            if all(by_key[dep].status == ResearchTaskStatus.COMPLETED for dep in task.depends_on):
                ready.append(task)
        return sorted(ready, key=lambda item: (item.priority, item.task_key))

    def all_terminal(self) -> bool:
        return all(task.status in TERMINAL_RESEARCH_TASK_STATUSES for task in self.tasks)


def planner_tasks_from_questions(questions: list[str]) -> list[PlannerTask]:
    """Fallback when planner returns questions only."""
    return [
        PlannerTask(
            task_key=f"q{i + 1}",
            objective=text,
            question_text=text,
            depends_on=[],
            priority=i + 1,
        )
        for i, text in enumerate(questions)
    ]


def merge_planner_tasks(output_tasks: list[PlannerTask], questions: list[str]) -> list[PlannerTask]:
    if output_tasks:
        return output_tasks
    return planner_tasks_from_questions(questions)


def task_keys_for_ids(tasks: list[ResearchTaskRead]) -> dict[UUID, str]:
    return {task.id: task.task_key for task in tasks}
