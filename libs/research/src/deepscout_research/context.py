"""Context assembly foundation — phase-scoped model inputs."""

from dataclasses import dataclass, field
from uuid import UUID

from deepscout_core.domain.enums import ResearchPhase


@dataclass(slots=True)
class ContextAssembly:
    """Bounded context for a single model call."""

    run_id: UUID
    phase: ResearchPhase
    goal: str
    system_policy: str
    phase_instructions: str
    domain_state: dict[str, str] = field(default_factory=dict)
    retrieved_data: list[str] = field(default_factory=list)

    def render_user_content(self) -> str:
        from deepscout_research.prompts.render import compose_runtime_context

        return compose_runtime_context(
            goal=self.goal,
            domain_state=self.domain_state,
            retrieved_data=self.retrieved_data or None,
        )
