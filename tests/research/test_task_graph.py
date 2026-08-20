"""Tests for research task DAG."""

from uuid import uuid4

import pytest
from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import ResearchTaskRead
from deepscout_research.tasks.graph import TaskGraph, TaskGraphError, merge_planner_tasks


def test_merge_planner_tasks_from_questions() -> None:
    tasks = merge_planner_tasks([], ["Question A", "Question B"])
    assert len(tasks) == 2
    assert tasks[0].task_key == "q1"


def test_task_graph_cycle_detection() -> None:
    task_a = ResearchTaskRead(
        id=uuid4(),
        task_key="a",
        objective="A",
        status=ResearchTaskStatus.PENDING,
        priority=1,
        depends_on=["b"],
        allowed_tools=["web_search"],
    )
    task_b = ResearchTaskRead(
        id=uuid4(),
        task_key="b",
        objective="B",
        status=ResearchTaskStatus.PENDING,
        priority=2,
        depends_on=["a"],
        allowed_tools=["web_search"],
    )
    graph = TaskGraph((task_a, task_b))
    with pytest.raises(TaskGraphError):
        graph.validate_dependencies()


def test_ready_tasks_respects_dependencies() -> None:
    task_a = ResearchTaskRead(
        id=uuid4(),
        task_key="a",
        objective="A",
        status=ResearchTaskStatus.PENDING,
        priority=1,
        depends_on=[],
        allowed_tools=["web_search"],
    )
    task_b = ResearchTaskRead(
        id=uuid4(),
        task_key="b",
        objective="B",
        status=ResearchTaskStatus.PENDING,
        priority=2,
        depends_on=["a"],
        allowed_tools=["web_search"],
    )
    graph = TaskGraph((task_a, task_b))
    ready = graph.ready_tasks()
    assert [task.task_key for task in ready] == ["a"]
