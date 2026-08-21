"""Bounded context lifecycle: write, select, compact, isolate, assemble, measure."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from deepscout_core.domain.enums import ResearchPhase


@dataclass(slots=True)
class ContextBudget:
    """Soft token budget for one model call. Estimates use chars/4."""

    max_input_tokens: int = 8000
    output_reserve: int = 1024
    retrieved_share: float = 0.45
    working_share: float = 0.20
    history_share: float = 0.15

    def remaining_for_generation(self, used_tokens: int) -> int:
        return max(0, self.max_input_tokens - self.output_reserve - used_tokens)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


@dataclass(slots=True)
class ContextAssembly:
    """Bounded context for a single model call. Privileged vs DATA stay split."""

    run_id: UUID
    phase: ResearchPhase
    goal: str
    system_policy: str
    phase_instructions: str
    domain_state: dict[str, str] = field(default_factory=dict)
    retrieved_data: list[str] = field(default_factory=list)
    working_state: dict[str, str] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)
    skill_instructions: str = ""
    tool_descriptions: str = ""
    budget: ContextBudget = field(default_factory=ContextBudget)
    compacted: bool = False
    chars_before: int = 0
    chars_after: int = 0

    def isolate_worker(self, *, objective: str, allowed_tools: list[str]) -> ContextAssembly:
        """Subagent isolation: task slice only — no global trace dump."""
        return ContextAssembly(
            run_id=self.run_id,
            phase=self.phase,
            goal=self.goal,
            system_policy=self.system_policy,
            phase_instructions=self.phase_instructions,
            domain_state={
                "task_objective": objective,
                "allowed_tools": ", ".join(allowed_tools) or "none",
            },
            retrieved_data=[],
            working_state={},
            artifact_refs=[],
            skill_instructions="",
            tool_descriptions="",
            budget=self.budget,
        )

    def compact(self, *, char_limit: int) -> ContextAssembly:
        from deepscout_research.runtime.compaction import compact_retrieved

        before = self._dynamic_chars()
        retrieved, refs, dropped = compact_retrieved(self.retrieved_data, char_limit=char_limit)
        compacted = ContextAssembly(
            run_id=self.run_id,
            phase=self.phase,
            goal=self.goal,
            system_policy=self.system_policy,
            phase_instructions=self.phase_instructions,
            domain_state=dict(self.domain_state),
            retrieved_data=retrieved,
            working_state=dict(self.working_state),
            artifact_refs=list(dict.fromkeys([*self.artifact_refs, *refs])),
            skill_instructions=self.skill_instructions,
            tool_descriptions=self.tool_descriptions,
            budget=self.budget,
            compacted=before > char_limit or dropped > 0,
            chars_before=before,
            chars_after=0,
        )
        compacted.chars_after = compacted._dynamic_chars()
        return compacted

    def _dynamic_chars(self) -> int:
        parts = [
            self.goal,
            *self.domain_state.values(),
            *self.retrieved_data,
            *self.working_state.values(),
            self.skill_instructions,
            self.tool_descriptions,
        ]
        return sum(len(part) for part in parts)

    def measured_tokens(self) -> dict[str, int]:
        system = estimate_tokens(self.system_policy) + estimate_tokens(self.phase_instructions)
        tools = estimate_tokens(self.tool_descriptions)
        skills = estimate_tokens(self.skill_instructions)
        working = estimate_tokens("\n".join(self.working_state.values()))
        retrieved = estimate_tokens("\n".join(self.retrieved_data))
        history = estimate_tokens("\n".join(self.domain_state.values()))
        return {
            "system": system,
            "tools": tools,
            "skills": skills,
            "working": working,
            "retrieved": retrieved,
            "history": history,
            "total": system + tools + skills + working + retrieved + history,
        }

    def render_user_content(self) -> str:
        from deepscout_research.prompts.render import compose_runtime_context

        domain = dict(self.domain_state)
        if self.working_state:
            domain["working_state"] = "\n".join(f"{k}: {v}" for k, v in self.working_state.items())
        if self.artifact_refs:
            domain["artifact_refs"] = ", ".join(self.artifact_refs)
        if self.skill_instructions:
            domain["skill_procedure"] = self.skill_instructions
        if self.tool_descriptions:
            domain["available_tools"] = self.tool_descriptions
        return compose_runtime_context(
            goal=self.goal,
            domain_state=domain,
            retrieved_data=self.retrieved_data or None,
        )
