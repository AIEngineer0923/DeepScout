from deepscout_core.domain.enums import PlanDecomposition
from deepscout_core.domain.schemas import PlannerOutput, PlannerQuestion, PlannerTask
from deepscout_research.planner import planner_output_to_write
from deepscout_research.runtime.dag_quality import evaluate_plan_dag
from deepscout_research.runtime.plan_repair import repair_plan


def test_simple_collapses_extra_tasks() -> None:
    output = PlannerOutput(
        approach="Look up the names.",
        success_criteria="Two chemistry names.",
        decomposition=PlanDecomposition.SIMPLE,
        tasks=[
            PlannerTask(task_key="q1", objective="Name chemistries", priority=1),
            PlannerTask(task_key="q2", objective="Also list vendors", priority=2),
        ],
    )
    repaired = repair_plan(output)
    assert len(repaired.tasks) == 1
    assert repaired.tasks[0].depends_on == []
    quality = evaluate_plan_dag(output)
    assert quality["pass"] is True
    assert quality["task_count"] == 1


def test_legacy_questions_are_not_collapsed() -> None:
    output = PlannerOutput(
        approach="Compare chemistries",
        success_criteria="Tradeoffs",
        questions=[
            PlannerQuestion(text="Energy density?", priority=1),
            PlannerQuestion(text="Safety?", priority=2),
        ],
    )
    repaired = repair_plan(output)
    assert len(repaired.tasks) == 2
    assert all(not task.depends_on for task in repaired.tasks)


def test_chain_adds_missing_dependencies() -> None:
    output = PlannerOutput(
        approach="Identify then retrieve.",
        success_criteria="Statute text for the named act.",
        decomposition=PlanDecomposition.CHAIN,
        tasks=[
            PlannerTask(task_key="find", objective="Identify the controlling statute", priority=1),
            PlannerTask(
                task_key="read",
                objective="Extract obligations from that statute",
                priority=2,
            ),
        ],
    )
    repaired = repair_plan(output)
    assert repaired.tasks[-1].depends_on == ["find"]
    quality = evaluate_plan_dag(output)
    assert quality["pass"] is True
    assert quality["critical_path_depth"] >= 2


def test_mixed_fan_in() -> None:
    output = PlannerOutput(
        approach="Independent then synthesize.",
        success_criteria="A comparison.",
        decomposition=PlanDecomposition.MIXED,
        tasks=[
            PlannerTask(task_key="a", objective="Profile chemistry A", priority=1),
            PlannerTask(task_key="b", objective="Profile chemistry B", priority=2),
            PlannerTask(
                task_key="syn",
                objective="Compare A and B from prior findings",
                priority=3,
            ),
        ],
    )
    repaired = repair_plan(output)
    by_key = {task.task_key: task for task in repaired.tasks}
    assert by_key["a"].depends_on == []
    assert by_key["b"].depends_on == []
    assert set(by_key["syn"].depends_on) == {"a", "b"}
    write = planner_output_to_write(output)
    assert len(write.tasks) == 3


def test_duplicate_objectives_merge() -> None:
    output = PlannerOutput(
        approach="One question twice.",
        success_criteria="Done",
        decomposition=PlanDecomposition.PARALLEL,
        tasks=[
            PlannerTask(task_key="q1", objective="What is LFP?"),
            PlannerTask(task_key="q2", objective="What is LFP?"),
        ],
    )
    repaired = repair_plan(output)
    assert len(repaired.tasks) == 1


def test_self_dependency_removed() -> None:
    output = PlannerOutput(
        approach="Broken",
        success_criteria="Fixed",
        decomposition=PlanDecomposition.PARALLEL,
        tasks=[
            PlannerTask(task_key="q1", objective="Lookup A", depends_on=["q1"]),
            PlannerTask(task_key="q2", objective="Lookup B", depends_on=["q2"]),
        ],
    )
    quality = evaluate_plan_dag(output)
    assert quality["self_dependency"] is False
    assert quality["pass"] is True
