"""Runtime policy reader — bounded hooks for promoted learning policies."""

from __future__ import annotations

from uuid import UUID

from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.policy import (
    DEFAULT_BASELINE_POLICY,
    gap_queries_per_round_bonus,
)

_GLOBAL_POLICY_KEY = "global.corrective_research"


def get_active_policy_payload(
    store: ResearchStore,
    *,
    policy_key: str = _GLOBAL_POLICY_KEY,
    owner_principal_id: UUID | None = None,
) -> dict:
    if not store.learning_tables_available():
        return dict(DEFAULT_BASELINE_POLICY)
    active = store.get_active_learning_policy(
        policy_key=policy_key, owner_principal_id=owner_principal_id
    )
    if active is None:
        return dict(DEFAULT_BASELINE_POLICY)
    return {**DEFAULT_BASELINE_POLICY, **(active.get("payload") or {})}


def corrective_gap_queries_bonus(
    store: ResearchStore,
    *,
    owner_principal_id: UUID | None = None,
) -> int:
    payload = get_active_policy_payload(store, owner_principal_id=owner_principal_id)
    return gap_queries_per_round_bonus(payload)
