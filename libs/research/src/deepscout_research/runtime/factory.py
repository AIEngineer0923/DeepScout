"""Typed agent/worker factory — never instantiates from arbitrary model strings."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from deepscout_core.domain.enums import AgentRole
from deepscout_core.domain.schemas import ResearchTaskRead

from deepscout_research.runtime.delegation import DelegationPolicy
from deepscout_research.tools.registry import describe_tools, resolve_tools


@dataclass(frozen=True, slots=True)
class AgentSpec:
    role: AgentRole
    task_id: UUID
    objective: str
    allowed_tools: tuple[str, ...]
    skill_ids: tuple[str, ...]
    tool_descriptions: str
    parent_task_id: UUID | None
    depth: int
    max_steps: int


def build_worker_spec(
    task: ResearchTaskRead,
    *,
    skill_ids: list[str],
    depth: int,
    policy: DelegationPolicy,
    parent_task_id: UUID | None = None,
) -> AgentSpec:
    if depth > policy.max_depth:
        raise PermissionError("delegation depth exceeded")
    tools = resolve_tools(task.allowed_tools)
    return AgentSpec(
        role=AgentRole.RESEARCH_WORKER,
        task_id=task.id,
        objective=task.objective,
        allowed_tools=tools,
        skill_ids=tuple(skill_ids[:2]),
        tool_descriptions=describe_tools(tools),
        parent_task_id=parent_task_id,
        depth=depth,
        max_steps=3,
    )
