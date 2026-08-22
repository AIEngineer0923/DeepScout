"""Resolve frozen learning policy for a research run."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_evaluation.learning.policy_families import EffectiveRuntimePolicy
from deepscout_evaluation.learning.policy_runtime import policy_from_run_snapshot
from deepscout_persistence.store import ResearchStore
from deepscout_providers.config import ModelBuildOptions, options_from_settings

from deepscout_research.routing.model_router import ModelRouter


def effective_policy_for_run(store: ResearchStore, run_id: UUID) -> EffectiveRuntimePolicy | None:
    row = store.get_run_row(run_id)
    return policy_from_run_snapshot(row.config_snapshot if row else None)


def model_router_for_run(
    settings: Settings,
    store: ResearchStore,
    run_id: UUID,
    *,
    health=None,
) -> ModelRouter:
    return ModelRouter(
        settings,
        health=health,
        effective_policy=effective_policy_for_run(store, run_id),
    )


def model_build_options_for_run(
    settings: Settings,
    store: ResearchStore,
    run_id: UUID,
) -> ModelBuildOptions:
    from deepscout_evaluation.learning.policy_runtime import effective_reasoning_effort

    base = options_from_settings(settings)
    effective = effective_policy_for_run(store, run_id)
    effort = effective_reasoning_effort(effective)
    if effort:
        return ModelBuildOptions(
            temperature=base.temperature,
            max_tokens=base.max_tokens,
            reasoning_effort=effort,
        )
    return base
