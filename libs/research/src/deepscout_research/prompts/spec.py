"""Versioned prompt specifications for DeepScout runtime agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from deepscout_core.domain.enums import AgentRole


class PromptStatus(StrEnum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class PromptSpec:
    prompt_id: str
    prompt_version: str
    role: AgentRole
    responsibility: str
    input_contract: str
    output_contract: str
    context_policy: str
    tool_policy: str
    termination_expectations: str
    evaluator_coverage: tuple[str, ...]
    instructions: str
    status: PromptStatus = PromptStatus.ACTIVE
    schema_version: str = "1"
    compatible_providers: tuple[str, ...] = ("google", "openai", "anthropic")
    evaluation_baseline: str | None = None
    few_shot_examples: tuple[str, ...] = ()

    def trace_metadata(self) -> dict[str, str]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "prompt_status": self.status.value,
            "schema_version": self.schema_version,
            "agent_role": self.role.value,
        }
