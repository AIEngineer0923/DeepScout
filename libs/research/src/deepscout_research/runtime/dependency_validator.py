"""Bounded semantic dependency validation. One LLM call, no recursive replanning."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import AgentRole, PlanDecomposition, ResearchPhase
from deepscout_core.domain.schemas import (
    DependencyValidatorOutput,
    PlannerOutput,
    PlannerQuestion,
    PlannerTask,
)
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_providers.config import application_retry_policy
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from deepscout_research.context import ContextAssembly
from deepscout_research.prompts import DEPENDENCY_VALIDATOR_V1, compose_system_message
from deepscout_research.retry import run_with_retry
from deepscout_research.routing.model_router import ModelRouter
from deepscout_research.runtime.plan_repair import repair_plan
from deepscout_research.trace_redaction import redact_trace_inputs
from deepscout_research.usage.recorder import langsmith_metadata, record_model_usage

MAX_VALIDATOR_TASKS = 8
LAST_DIAGNOSTICS: dict = {}


def apply_validator_output(base: PlannerOutput, validated: DependencyValidatorOutput) -> PlannerOutput:
    """Merge validator DAG onto planner output. Structural repair still runs after this."""
    try:
        decomposition = PlanDecomposition(validated.decomposition.strip().lower())
    except ValueError:
        decomposition = base.decomposition
    if validated.false_simple and decomposition == PlanDecomposition.SIMPLE:
        decomposition = PlanDecomposition.CHAIN if len(validated.tasks) >= 2 else decomposition
    by_key = {task.task_key: task for task in base.tasks}
    merged: list[PlannerTask] = []
    for index, item in enumerate(validated.tasks[:MAX_VALIDATOR_TASKS], start=1):
        key = "".join(ch for ch in item.task_key.lower() if ch.isalnum() or ch in "_-") or f"t{index}"
        existing = by_key.get(key)
        objective = item.objective or (existing.objective if existing else key)
        merged.append(
            PlannerTask(
                task_key=key[:64],
                objective=objective,
                question_text=objective,
                depends_on=[dep[:64] for dep in item.depends_on],
                priority=min(5, max(1, int(item.priority or (existing.priority if existing else 3)))),
                dependency_reason=(item.dependency_reason or "")[:500],
                parallel_safe=bool(item.parallel_safe),
            )
        )
    if not merged:
        merged = list(base.tasks)
        if validated.false_simple and decomposition == PlanDecomposition.SIMPLE and len(merged) == 1:
            decomposition = PlanDecomposition.CHAIN
    return base.model_copy(
        update={
            "decomposition": decomposition,
            "tasks": merged,
            "questions": [
                PlannerQuestion(text=task.question_text or task.objective, priority=task.priority)
                for task in merged
            ],
        }
    )


@traceable(
    name="phase:plan_validate",
    run_type="chain",
    process_inputs=redact_trace_inputs,
    metadata=DEPENDENCY_VALIDATOR_V1.trace_metadata(),
)
def validate_semantic_dependencies(
    settings: Settings,
    *,
    run_id: UUID,
    goal: str,
    output: PlannerOutput,
    store: ResearchStore | None = None,
    invoke=None,
) -> tuple[PlannerOutput, dict]:
    """Return (corrected plan, diagnostics). Falls back to input plan on validator failure."""
    diagnostics = {
        "initial_decomposition": output.decomposition.value,
        "validator_applied": False,
        "false_simple": False,
        "notes": "",
        "error": None,
    }
    if output.decomposition == PlanDecomposition.UNSPECIFIED:
        return output, diagnostics
    payload = {
        "goal": goal,
        "decomposition": output.decomposition.value,
        "tasks": [
            {
                "task_key": task.task_key,
                "objective": task.objective,
                "depends_on": list(task.depends_on),
                "required_inputs": task.required_inputs,
                "produced_output": task.produced_output,
            }
            for task in output.tasks
        ],
    }
    try:
        if invoke is None:
            router = ModelRouter(settings)
            model, selection = router.build_chat_model(AgentRole.PLANNER_VALIDATOR)
            structured = model.with_structured_output(DependencyValidatorOutput, include_raw=True)
            context = ContextAssembly(
                run_id=run_id,
                phase=ResearchPhase.PLAN,
                goal=goal,
                system_policy=compose_system_message(DEPENDENCY_VALIDATOR_V1),
                phase_instructions=(
                    "Correct information dependencies. Split false-simple plans. "
                    "Do not invent sources, budgets, monitors, or tool permissions."
                ),
                domain_state={"planner_json": str(payload)[:6000]},
            )
            messages = [
                SystemMessage(content=compose_system_message(DEPENDENCY_VALIDATOR_V1)),
                HumanMessage(content=context.render_user_content()),
            ]
            trace_meta = langsmith_metadata(
                prompt=DEPENDENCY_VALIDATOR_V1, selection=selection, run_id=run_id
            )

            def _invoke() -> object:
                return structured.invoke(messages, config={"metadata": trace_meta})

            raw_result = run_with_retry(_invoke, policy=application_retry_policy(settings))
            if isinstance(raw_result, dict):
                parsed = raw_result.get("parsed")
                raw_message = raw_result.get("raw")
            else:
                parsed = raw_result
                raw_message = None
            if store is not None and raw_message is not None:
                record_model_usage(
                    store,
                    settings,
                    message=raw_message,
                    run_id=run_id,
                    phase=ResearchPhase.PLAN,
                    role=AgentRole.PLANNER_VALIDATOR,
                    selection=selection,
                    prompt=DEPENDENCY_VALIDATOR_V1,
                )
        else:
            parsed = invoke(payload)
        if not isinstance(parsed, DependencyValidatorOutput):
            parsed = DependencyValidatorOutput.model_validate(parsed)
        corrected = apply_validator_output(output, parsed)
        diagnostics.update(
            {
                "validator_applied": True,
                "false_simple": parsed.false_simple,
                "notes": parsed.notes[:500],
                "validator_decomposition": parsed.decomposition,
            }
        )
        return corrected, diagnostics
    except Exception as exc:
        diagnostics["error"] = type(exc).__name__
        return output, diagnostics


def finalize_plan(
    settings: Settings,
    *,
    run_id: UUID,
    goal: str,
    output: PlannerOutput,
    store: ResearchStore | None = None,
    invoke=None,
) -> tuple[PlannerOutput, dict]:
    validated, diagnostics = validate_semantic_dependencies(
        settings, run_id=run_id, goal=goal, output=output, store=store, invoke=invoke
    )
    repaired = repair_plan(validated)
    diagnostics["final_decomposition"] = repaired.decomposition.value
    diagnostics["final_task_count"] = len(repaired.tasks)
    diagnostics["final_edges"] = [
        {"task_key": task.task_key, "depends_on": list(task.depends_on)} for task in repaired.tasks
    ]
    LAST_DIAGNOSTICS.clear()
    LAST_DIAGNOSTICS.update(diagnostics)
    return repaired, diagnostics
