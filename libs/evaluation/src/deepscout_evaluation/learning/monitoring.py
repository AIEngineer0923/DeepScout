"""Post-promotion monitoring and safe automatic rollback for low-risk policies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.policy_families import FAMILY_RISK, PolicyFamily, PolicyRiskLevel

MONITORING_WINDOW_HOURS = 72
MIN_MONITORING_SAMPLES = 5
CRITICAL_REGRESSION_THRESHOLD = 0.15


def start_policy_monitoring(
    store: ResearchStore,
    *,
    policy_version_id: UUID,
    policy_key: str,
    policy_family: str,
    owner_principal_id: UUID | None,
    baseline_metrics: dict[str, Any],
) -> UUID | None:
    return store.start_learning_policy_monitoring(
        policy_version_id=policy_version_id,
        policy_key=policy_key,
        policy_family=policy_family,
        owner_principal_id=owner_principal_id,
        baseline_metrics=baseline_metrics,
        window_end=datetime.now(UTC) + timedelta(hours=MONITORING_WINDOW_HOURS),
    )


def record_monitoring_observation(
    store: ResearchStore,
    *,
    policy_key: str,
    owner_principal_id: UUID | None,
    metrics: dict[str, Any],
) -> None:
    store.record_policy_monitoring_observation(
        policy_key=policy_key,
        owner_principal_id=owner_principal_id,
        metrics=metrics,
    )


def evaluate_monitoring_rollback(store: ResearchStore) -> list[dict[str, Any]]:
    """Auto-rollback LOW_RISK policies when critical regression detected."""
    actions: list[dict[str, Any]] = []
    for window in store.list_active_policy_monitoring():
        family = PolicyFamily(window["policy_family"])
        if FAMILY_RISK[family] != PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE:
            continue
        if int(window.get("observed_samples", 0)) < MIN_MONITORING_SAMPLES:
            continue
        baseline_q = float((window.get("baseline_metrics") or {}).get("quality", 0.0))
        observed_q = float((window.get("observed_metrics") or {}).get("avg_quality", baseline_q))
        if baseline_q - observed_q < CRITICAL_REGRESSION_THRESHOLD:
            continue
        if store.promotion_cooldown_active(
            policy_key=window["policy_key"],
            owner_principal_id=window.get("owner_principal_id"),
        ):
            continue
        rolled = store.rollback_learning_policy(
            policy_key=window["policy_key"],
            owner_principal_id=window.get("owner_principal_id"),
            rollback_reason="auto_rollback_quality_regression",
            actor="monitoring",
        )
        if rolled:
            store.complete_policy_monitoring(window["id"], status="auto_rolled_back")
            store._record_learning_audit(
                event_type="policy_auto_rollback",
                policy_key=window["policy_key"],
                policy_family=window["policy_family"],
                owner_principal_id=window.get("owner_principal_id"),
                policy_version_id=window.get("policy_version_id"),
                reason="critical quality regression during monitoring window",
                details={
                    "baseline_quality": baseline_q,
                    "observed_quality": observed_q,
                    "samples": window.get("observed_samples"),
                },
            )
            actions.append({"policy_key": window["policy_key"], "action": "auto_rollback"})
    return actions


def run_metrics_from_evaluations(
    evaluation_rows: list[dict[str, Any]],
    *,
    consumption: dict[str, Any] | None = None,
) -> dict[str, Any]:
    passed = sum(1 for row in evaluation_rows if str(row.get("status")) == "passed")
    total = len(evaluation_rows) or 1
    return {
        "quality": passed / total,
        "cost": float((consumption or {}).get("tool_calls", 0)),
        "latency_ms": float((consumption or {}).get("duration_ms", 0)),
        "critical_failures": sum(
            1 for row in evaluation_rows if str(row.get("status")) in {"failed", "error"}
        ),
    }
