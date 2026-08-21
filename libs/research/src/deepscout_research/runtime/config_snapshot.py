"""Frozen run configuration for reproducibility (not a security downgrade vector)."""

from __future__ import annotations

from deepscout_core.settings import Settings

from deepscout_research.prompts.registry import PROMPT_REGISTRY


def build_config_snapshot(settings: Settings) -> dict:
    prompts = {
        spec.prompt_id: spec.prompt_version
        for spec in PROMPT_REGISTRY.values()
    }
    return {
        "state_schema_version": 8,
        "hitl_policy_version": "hitl-v1",
        "context_policy_version": "ctx-v1",
        "tool_registry_version": "1",
        "skill_policy": "auto" if settings.agent_skills_auto else "off",
        "max_delegation_depth": settings.agent_max_delegation_depth,
        "max_replans": settings.agent_max_replans,
        "prompts": prompts,
        "llm_provider": settings.llm_provider.value,
        "retrieval_enabled": True,
        "retry_owner": "application",
        "provider_transport_max_retries": 0,
    }
