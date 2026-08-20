"""Versioned DeepScout runtime prompt architecture."""

from deepscout_research.prompts.registry import (
    CRITIC_V1,
    EXTRACTOR_V1,
    PLANNER_V1,
    REPORT_V1,
    RESEARCH_WORKER_V1,
    SYNTHESIS_V1,
    VERIFIER_V1,
    compose_system_message,
    get_prompt,
)
from deepscout_research.prompts.render import compose_runtime_context
from deepscout_research.prompts.spec import PromptSpec, PromptStatus

__all__ = [
    "CRITIC_V1",
    "EXTRACTOR_V1",
    "PLANNER_V1",
    "REPORT_V1",
    "RESEARCH_WORKER_V1",
    "SYNTHESIS_V1",
    "VERIFIER_V1",
    "PromptSpec",
    "PromptStatus",
    "compose_runtime_context",
    "compose_system_message",
    "get_prompt",
]
