"""Rollback for learning policy versions."""

from __future__ import annotations

from uuid import uuid4

from deepscout_persistence.models import LearningPolicyVersionRow
from deepscout_persistence.store import ResearchStore


def test_rollback_learning_policy_restores_previous(db_session) -> None:
    store = ResearchStore(db_session)
    if not store.learning_tables_available():
        return
    key = f"test.rollback.{uuid4().hex[:8]}"
    store.promote_learning_policy(
        policy_key=key,
        version_label="v1",
        payload={"gap_queries_per_round_bonus": 1},
        owner_principal_id=None,
        promoted_from_candidate_id=None,
        promotion_reason="v1",
        evidence={},
    )
    store.promote_learning_policy(
        policy_key=key,
        version_label="v2",
        payload={"gap_queries_per_round_bonus": 0},
        owner_principal_id=None,
        promoted_from_candidate_id=None,
        promotion_reason="v2",
        evidence={},
    )
    rolled = store.rollback_learning_policy(
        policy_key=key,
        owner_principal_id=None,
        rollback_reason="test",
    )
    assert rolled is not None
    active = store.get_active_learning_policy(policy_key=key, owner_principal_id=None)
    assert active is not None
    assert active["version_label"] == "v1"
    assert active["payload"]["gap_queries_per_round_bonus"] == 1
    inactive = db_session.get(LearningPolicyVersionRow, rolled)
    assert inactive is not None
    assert inactive.active is True
