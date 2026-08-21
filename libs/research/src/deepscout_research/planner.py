"""Research planner — structured output, no web tools."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import AgentRole, ResearchPhase
from deepscout_core.domain.schemas import PlannerOutput, ResearchPlanWrite
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_providers.config import application_retry_policy
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from deepscout_research.context import ContextAssembly
from deepscout_research.prompts import PLANNER_V1, compose_system_message
from deepscout_research.retry import run_with_retry
from deepscout_research.routing.model_router import ModelRouter
from deepscout_research.tasks.graph import merge_planner_tasks
from deepscout_research.trace_redaction import redact_trace_inputs
from deepscout_research.usage.recorder import langsmith_metadata, record_model_usage


@traceable(
    name="phase:plan",
    run_type="chain",
    process_inputs=redact_trace_inputs,
    metadata=PLANNER_V1.trace_metadata(),
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
    router = ModelRouter(settings)
    model, selection = router.build_chat_model(AgentRole.PLANNER)
    structured_model = model.with_structured_output(PlannerOutput, include_raw=True)
    language_note = (
        f"Write planner approach, success criteria, and research questions in {output_language}. "
        "This is the research output language, not the product UI language."
    )
    context = ContextAssembly(
        run_id=run_id,
        phase=ResearchPhase.PLAN,
        goal=goal,
        system_policy=compose_system_message(PLANNER_V1),
        phase_instructions="Create 2-5 prioritized research questions.",
        domain_state={"budget": budget_summary, "output_language": language_note},
    )
    if settings.agent_skills_auto:
        from deepscout_research.skills.loader import skill_catalog_for_prompt

        context.domain_state["skill_catalog"] = skill_catalog_for_prompt()
    messages = [
        SystemMessage(content=compose_system_message(PLANNER_V1)),
        HumanMessage(content=context.render_user_content()),
    ]
    trace_meta = langsmith_metadata(prompt=PLANNER_V1, selection=selection, run_id=run_id)

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
            prompt=PLANNER_V1,
        )
    if not isinstance(parsed, PlannerOutput):
        return PlannerOutput.model_validate(parsed)
    return parsed


def planner_output_to_write(output: PlannerOutput) -> ResearchPlanWrite:
    ordered = sorted(output.questions, key=lambda item: item.priority)
    questions = [question.text for question in ordered]
    tasks = merge_planner_tasks([], questions)
    return ResearchPlanWrite(
        strategy=output.approach,
        success_criteria=output.success_criteria,
        questions=questions,
        tasks=tasks,
    )
