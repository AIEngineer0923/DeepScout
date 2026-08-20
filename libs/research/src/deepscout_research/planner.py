"""Research planner — structured output, no web tools."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import ResearchPhase
from deepscout_core.domain.schemas import PlannerOutput, ResearchPlanWrite
from deepscout_core.settings import Settings
from deepscout_providers.factory import build_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from deepscout_research.context import ContextAssembly
from deepscout_research.tasks.graph import merge_planner_tasks
from deepscout_research.trace_redaction import redact_trace_inputs

PLANNER_SYSTEM = (
    "You are DeepScout research planner. Produce a concise structured plan only. "
    "Do not browse the web. Do not claim to have verified facts. "
    "Return actionable research questions with priorities."
)


@traceable(name="phase:plan", run_type="chain", process_inputs=redact_trace_inputs)
def build_research_plan(
    settings: Settings,
    *,
    run_id: UUID,
    goal: str,
    budget_summary: str,
) -> PlannerOutput:
    model = build_chat_model(settings)
    structured_model = model.with_structured_output(PlannerOutput)
    context = ContextAssembly(
        run_id=run_id,
        phase=ResearchPhase.PLAN,
        goal=goal,
        system_policy=PLANNER_SYSTEM,
        phase_instructions="Create 2-5 prioritized research questions.",
        domain_state={"budget": budget_summary},
    )
    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=context.render_user_content()),
    ]
    result = structured_model.invoke(messages)
    if not isinstance(result, PlannerOutput):
        return PlannerOutput.model_validate(result)
    return result


def planner_output_to_write(output: PlannerOutput) -> ResearchPlanWrite:
    ordered = sorted(output.questions, key=lambda item: item.priority)
    questions = [question.text for question in ordered]
    tasks = merge_planner_tasks(output.tasks, questions)
    return ResearchPlanWrite(
        strategy=output.approach,
        success_criteria=output.success_criteria,
        questions=questions,
        tasks=tasks,
    )
