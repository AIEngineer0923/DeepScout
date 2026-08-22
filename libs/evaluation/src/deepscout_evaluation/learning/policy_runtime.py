"""Runtime policy reader — bounded hooks for all promoted policy families."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.policy import (
    allocation_parallel_preference,
    authority_namespace_diversification,
    evidence_sufficiency_threshold_delta,
    gap_queries_per_round_bonus,
    low_marginal_yield_threshold_delta,
    max_tasks_bonus,
    planner_decomposition_strictness,
    prefer_lower_cost_strategy,
    reasoning_effort_from_policy,
    report_rewrite_bonus,
    retrieval_candidate_k_multiplier,
    retrieval_top_k_delta,
    search_variant_count_delta,
    zero_yield_reformulation_bonus,
)
from deepscout_evaluation.learning.policy_families import (
    EffectivePolicyVersionRef,
    EffectiveRuntimePolicy,
    PolicyFamily,
)
from deepscout_evaluation.learning.policy_resolver import resolve_effective_runtime_policy

_GLOBAL_POLICY_KEY = "global.corrective_research"


def resolve_runtime_policy(
    store: ResearchStore,
    settings: Settings,
    *,
    owner_principal_id: UUID | None = None,
    retrieval_intent: str | None = None,
) -> EffectiveRuntimePolicy:
    return resolve_effective_runtime_policy(
        store,
        settings,
        owner_principal_id=owner_principal_id,
        retrieval_intent=retrieval_intent,
    )


def get_active_policy_payload(
    store: ResearchStore,
    *,
    policy_key: str = _GLOBAL_POLICY_KEY,
    owner_principal_id: UUID | None = None,
) -> dict:
    """Legacy accessor — corrective research family only."""
    effective = resolve_effective_runtime_policy(
        store, Settings(), owner_principal_id=owner_principal_id
    )
    if policy_key == _GLOBAL_POLICY_KEY:
        return effective.corrective_research
    family = PolicyFamily.CORRECTIVE_RESEARCH
    for f in PolicyFamily:
        if policy_key.endswith(f.value):
            family = f
            break
    return effective.family_payload(family)


def corrective_gap_queries_bonus(
    store: ResearchStore,
    *,
    owner_principal_id: UUID | None = None,
    effective: EffectiveRuntimePolicy | None = None,
) -> int:
    payload = (
        effective.corrective_research
        if effective
        else resolve_effective_runtime_policy(
            store, Settings(), owner_principal_id=owner_principal_id
        ).corrective_research
    )
    return gap_queries_per_round_bonus(payload)


def effective_retrieval_top_k(
    store: ResearchStore,
    settings: Settings,
    base_top_k: int,
    *,
    owner_principal_id: UUID | None = None,
    effective: EffectiveRuntimePolicy | None = None,
) -> int:
    policy = effective or resolve_runtime_policy(
        store, settings, owner_principal_id=owner_principal_id
    )
    delta = retrieval_top_k_delta(policy.retrieval)
    return max(1, min(settings.retrieval_top_k + 3, base_top_k + delta))


def effective_retrieval_candidate_k(
    store: ResearchStore,
    settings: Settings,
    base_candidate_k: int,
    *,
    owner_principal_id: UUID | None = None,
    effective: EffectiveRuntimePolicy | None = None,
) -> int:
    policy = effective or resolve_runtime_policy(
        store, settings, owner_principal_id=owner_principal_id
    )
    mult = retrieval_candidate_k_multiplier(policy.retrieval)
    scaled = int(base_candidate_k * mult)
    return max(base_candidate_k, min(int(settings.retrieval_candidate_k * 1.25), scaled))


def effective_report_rewrite_limit(
    store: ResearchStore,
    settings: Settings,
    *,
    owner_principal_id: UUID | None = None,
    effective: EffectiveRuntimePolicy | None = None,
) -> int:
    policy = effective or resolve_runtime_policy(
        store, settings, owner_principal_id=owner_principal_id
    )
    bonus = report_rewrite_bonus(policy.synthesis)
    return min(
        settings.research_max_report_rewrites + 1, settings.research_max_report_rewrites + bonus
    )


def effective_allocation_parallelism(
    store: ResearchStore,
    settings: Settings,
    *,
    owner_principal_id: UUID | None = None,
    effective: EffectiveRuntimePolicy | None = None,
) -> float:
    policy = effective or resolve_runtime_policy(
        store, settings, owner_principal_id=owner_principal_id
    )
    return allocation_parallel_preference(policy.allocation)


def effective_prefer_lower_cost(
    store: ResearchStore,
    *,
    owner_principal_id: UUID | None = None,
    effective: EffectiveRuntimePolicy | None = None,
) -> bool:
    policy = effective or resolve_runtime_policy(
        store, Settings(), owner_principal_id=owner_principal_id
    )
    return prefer_lower_cost_strategy(policy.cost_latency)


def effective_query_strategy_params(
    effective: EffectiveRuntimePolicy | None,
) -> dict[str, int | float]:
    payload = effective.query_strategy if effective else {}
    return {
        "search_variant_count_delta": search_variant_count_delta(payload),
        "authority_namespace_diversification": authority_namespace_diversification(payload),
        "zero_yield_reformulation_bonus": zero_yield_reformulation_bonus(payload),
    }


def effective_sufficiency_params(
    effective: EffectiveRuntimePolicy | None,
) -> dict[str, float]:
    payload = effective.sufficiency if effective else {}
    return {
        "low_marginal_yield_threshold_delta": low_marginal_yield_threshold_delta(payload),
        "evidence_sufficiency_threshold_delta": evidence_sufficiency_threshold_delta(payload),
    }


def effective_planner_params(
    effective: EffectiveRuntimePolicy | None,
) -> dict[str, int | float]:
    payload = effective.planner if effective else {}
    return {
        "max_tasks_bonus": max_tasks_bonus(payload),
        "planner_decomposition_strictness": planner_decomposition_strictness(payload),
    }


def effective_reasoning_effort(
    effective: EffectiveRuntimePolicy | None,
) -> str | None:
    payload = effective.reasoning if effective else {}
    return reasoning_effort_from_policy(payload)


def effective_namespace_cap(effective: EffectiveRuntimePolicy | None) -> int:
    div = authority_namespace_diversification(
        effective.query_strategy if effective else {}
    )
    return max(1, min(3, round(1 + div * 2)))


def policy_from_run_snapshot(snapshot: dict | None) -> EffectiveRuntimePolicy | None:
    if not snapshot:
        return None
    block = snapshot.get("learning_policies")
    if not isinstance(block, dict):
        return None
    effective_block = block.get("effective")
    if not isinstance(effective_block, dict):
        return None
    versions_raw = block.get("learning_policy_versions") or []
    versions = [EffectivePolicyVersionRef(**v) for v in versions_raw if isinstance(v, dict)]
    kwargs = {family.value: effective_block.get(family.value, {}) for family in PolicyFamily}
    return EffectiveRuntimePolicy(versions=versions, **kwargs)


def retrieval_overrides_from_snapshot(
    snapshot: dict | None,
    settings: Settings,
) -> tuple[int | None, int | None]:
    """Return (top_k_override, candidate_k_override) from frozen run policy."""
    effective = policy_from_run_snapshot(snapshot)
    if effective is None:
        return None, None
    from deepscout_evaluation.learning.policy import (
        retrieval_candidate_k_multiplier,
        retrieval_top_k_delta,
    )

    base_top = settings.retrieval_top_k
    delta = retrieval_top_k_delta(effective.retrieval)
    top_k = max(1, min(base_top + 3, base_top + delta))
    mult = retrieval_candidate_k_multiplier(effective.retrieval)
    candidate_k = max(settings.retrieval_candidate_k, int(settings.retrieval_candidate_k * mult))
    candidate_k = min(int(settings.retrieval_candidate_k * 1.25), candidate_k)
    return top_k, candidate_k
