"""Policy resolution: hard limits > run constraints > promoted policy > defaults."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.policy_families import (
    FAMILY_BASELINES,
    LEGACY_POLICY_KEY,
    EffectivePolicyVersionRef,
    EffectiveRuntimePolicy,
    PolicyFamily,
    PolicyScope,
    clamp_payload,
    merge_baseline,
    policy_key_for,
)


def _read_family_policy(
    store: ResearchStore,
    family: PolicyFamily,
    *,
    owner_principal_id: UUID | None,
    scope_class: str | None = None,
) -> tuple[dict, EffectivePolicyVersionRef | None]:
    baseline = merge_baseline(family)
    keys_to_try: list[str] = []
    if scope_class:
        keys_to_try.append(
            policy_key_for(family, scope=PolicyScope.GLOBAL.value, class_suffix=scope_class)
        )
    keys_to_try.append(policy_key_for(family, scope=PolicyScope.GLOBAL.value))
    if owner_principal_id is not None:
        keys_to_try.append(policy_key_for(family, scope=PolicyScope.TENANT.value))
    if family == PolicyFamily.CORRECTIVE_RESEARCH:
        keys_to_try.insert(0, LEGACY_POLICY_KEY)

    for key in keys_to_try:
        owner = owner_principal_id if key.startswith("tenant.") else None
        active = store.get_active_learning_policy(policy_key=key, owner_principal_id=owner)
        if active is not None:
            payload = clamp_payload(
                {**baseline, **(active.get("payload") or {})},
                family=family,
            )
            ref = EffectivePolicyVersionRef(
                policy_family=family.value,
                policy_key=key,
                version_label=str(active.get("version_label", "unknown")),
                version_id=str(active.get("id")) if active.get("id") else None,
            )
            return payload, ref
    return baseline, None


def resolve_effective_runtime_policy(
    store: ResearchStore,
    settings: Settings,
    *,
    owner_principal_id: UUID | None = None,
    retrieval_intent: str | None = None,
) -> EffectiveRuntimePolicy:
    """Resolve all policy families for a research run."""
    if not store.learning_tables_available():
        return EffectiveRuntimePolicy(
            **{family.value: dict(FAMILY_BASELINES[family]) for family in PolicyFamily}
        )

    versions: list[EffectivePolicyVersionRef] = []
    family_payloads: dict[str, dict] = {}

    scope_class = None
    if retrieval_intent in {
        "identifier",
        "semantic",
        "entity_relation",
        "mixed",
        "global_thematic",
    }:
        scope_class = retrieval_intent

    for family in PolicyFamily:
        payload, ref = _read_family_policy(
            store,
            family,
            owner_principal_id=owner_principal_id,
            scope_class=scope_class if family == PolicyFamily.RETRIEVAL else None,
        )
        family_payloads[family.value] = payload
        if ref is not None:
            versions.append(ref)

    # Hard settings caps are applied at hook sites; record static caps for reproducibility.
    _ = settings  # precedence anchor for future run-specific overrides

    return EffectiveRuntimePolicy(versions=versions, **family_payloads)
