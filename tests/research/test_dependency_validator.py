from deepscout_core.domain.enums import PlanDecomposition
from deepscout_core.domain.schemas import (
    DependencyValidatorOutput,
    DependencyValidatorTask,
    PlannerOutput,
    PlannerTask,
)
from deepscout_research.runtime.dependency_validator import apply_validator_output, finalize_plan


def _plan() -> PlannerOutput:
    return PlannerOutput(
        approach="Find the person then duties.",
        success_criteria="Named officer plus duties.",
        decomposition=PlanDecomposition.SIMPLE,
        tasks=[
            PlannerTask(
                task_key="all",
                objective="Identify the UN Secretary-General and list duties",
            )
        ],
    )


def test_false_simple_is_split_into_chain() -> None:
    validated = DependencyValidatorOutput(
        decomposition="chain",
        false_simple=True,
        notes="Downstream duties require the named person.",
        tasks=[
            DependencyValidatorTask(
                task_key="identify",
                objective="Identify the current UN Secretary-General",
                depends_on=[],
                dependency_reason="",
                priority=1,
            ),
            DependencyValidatorTask(
                task_key="duties",
                objective="List statutory duties of the person identified",
                depends_on=["identify"],
                dependency_reason="Requires the named office-holder from identify",
                parallel_safe=False,
                priority=2,
            ),
        ],
    )
    merged = apply_validator_output(_plan(), validated)
    assert merged.decomposition == PlanDecomposition.CHAIN
    assert len(merged.tasks) == 2
    assert merged.tasks[1].depends_on == ["identify"]
    reason = merged.tasks[1].dependency_reason.lower()
    assert "named" in reason or "identify" in reason


def test_finalize_plan_uses_injected_validator() -> None:
    from deepscout_core.settings import Settings

    def invoke(_payload):
        return DependencyValidatorOutput(
            decomposition="chain",
            false_simple=True,
            notes="split",
            tasks=[
                DependencyValidatorTask(task_key="a", objective="Find entity", priority=1),
                DependencyValidatorTask(
                    task_key="b",
                    objective="Lookup attributes of that entity",
                    depends_on=["a"],
                    dependency_reason="Needs entity identity",
                    priority=2,
                ),
            ],
        )

    repaired, diagnostics = finalize_plan(
        Settings(_env_file=None),
        run_id=__import__("uuid").uuid4(),
        goal="Find X then duties of X",
        output=_plan(),
        invoke=invoke,
    )
    assert diagnostics["validator_applied"] is True
    assert diagnostics["false_simple"] is True
    assert repaired.decomposition == PlanDecomposition.CHAIN
    assert repaired.tasks[-1].depends_on == ["a"]
    assert diagnostics["final_task_count"] == 2
