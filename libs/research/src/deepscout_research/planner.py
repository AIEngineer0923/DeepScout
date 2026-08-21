"""Research planner — structured output, no web tools."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import AgentRole, PlanDecomposition, ResearchPhase
from deepscout_core.domain.schemas import (
    PlannerOutput,
    PlannerStructuredOutput,
    PlannerTask,
    ResearchPlanWrite,
)
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_providers.config import application_retry_policy
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from deepscout_research.context import ContextAssembly
from deepscout_research.prompts import PLANNER_V2, compose_system_message, get_prompt
from deepscout_research.retry import run_with_retry
from deepscout_research.routing.model_router import ModelRouter
from deepscout_research.runtime.plan_repair import repair_plan
from deepscout_research.trace_redaction import redact_trace_inputs
from deepscout_research.usage.recorder import langsmith_metadata, record_model_usage


@traceable(
    name="phase:plan",
    run_type="chain",
    process_inputs=redact_trace_inputs,
    metadata=PLANNER_V2.trace_metadata(),
)
def build_research_plan(
    settings: Settings,
    *,
    run_id: UUID,
    goal: str,
    budget_summary: str,
    store: ResearchStore | None = None,
    output_language: str = "en",
) -> PlannerOutput:
    try:
        planner_spec = get_prompt("planner", version=settings.planner_prompt_version)
    except KeyError:
        planner_spec = get_prompt("planner")
    router = ModelRouter(settings)
    model, selection = router.build_chat_model(AgentRole.PLANNER)
    structured_model = model.with_structured_output(PlannerStructuredOutput, include_raw=True)
    language_note = (
        f"Write planner approach, success criteria, and research questions in {output_language}. "
        "This is the research output language, not the product UI language."
    )
    phase_instructions = (
        "Classify decomposition, then emit the smallest valid DAG."
        if planner_spec.prompt_version != "1"
        else "Create 2-5 prioritized research questions."
    )
    context = ContextAssembly(
        run_id=run_id,
        phase=ResearchPhase.PLAN,
        goal=goal,
        system_policy=compose_system_message(planner_spec),
        phase_instructions=phase_instructions,
        domain_state={"budget": budget_summary, "output_language": language_note},
    )
    if settings.agent_skills_auto:
        from deepscout_research.skills.loader import skill_catalog_for_prompt

        context.domain_state["skill_catalog"] = skill_catalog_for_prompt()
    messages = [
        SystemMessage(content=compose_system_message(planner_spec)),
        HumanMessage(content=context.render_user_content()),
    ]
    trace_meta = langsmith_metadata(prompt=planner_spec, selection=selection, run_id=run_id)

    def _invoke() -> object:
        return structured_model.invoke(
            messages,
            config={"metadata": trace_meta},
        )

    # Application owns retries; LangChain transport max_retries is 0.
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
            role=AgentRole.PLANNER,
            selection=selection,
            prompt=planner_spec,
        )
    if not isinstance(parsed, PlannerStructuredOutput):
        parsed = PlannerStructuredOutput.model_validate(parsed)
    return repair_plan(_structured_to_planner_output(parsed))


def _structured_to_planner_output(parsed: PlannerStructuredOutput) -> PlannerOutput:
    try:
        decomposition = PlanDecomposition(parsed.decomposition.strip().lower())
    except ValueError:
        decomposition = PlanDecomposition.UNSPECIFIED
    tasks: list[PlannerTask] = []
    for index, task in enumerate(parsed.tasks, start=1):
        key = "".join(ch for ch in task.task_key.lower() if ch.isalnum() or ch in "_-") or f"t{index}"
        tasks.append(
            PlannerTask(
                task_key=key[:64],
                objective=task.objective,
                question_text=task.objective,
                depends_on=[dep[:64] for dep in task.depends_on],
                priority=min(5, max(1, int(task.priority or 3))),
            )
        )
    return PlannerOutput(
        approach=parsed.approach,
        success_criteria=parsed.success_criteria,
        decomposition=decomposition,
        questions=list(parsed.questions),
        tasks=tasks,
    )


def planner_output_to_write(output: PlannerOutput) -> ResearchPlanWrite:
    repaired = repair_plan(output)
    questions = [question.text for question in repaired.questions]
    return ResearchPlanWrite(
        strategy=repaired.approach,
        success_criteria=repaired.success_criteria,
        questions=questions,
        tasks=list(repaired.tasks),
    )
