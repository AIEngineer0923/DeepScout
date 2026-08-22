"""Learning experience store — tenant-scoped persistence."""

from __future__ import annotations

from uuid import UUID

from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.models import ImprovementCandidate, LearningCase, PolicyVersion


def persist_learning_case(store: ResearchStore, case: LearningCase) -> UUID:
    payload = case.to_store_dict()
    return store.upsert_learning_case(payload)


def persist_improvement_candidate(
    store: ResearchStore, candidate: ImprovementCandidate, *, learning_case_row_id: UUID
) -> UUID:
    payload = candidate.to_store_dict()
    payload["learning_case_row_id"] = learning_case_row_id
    return store.upsert_improvement_candidate(payload)


def promote_policy_version(store: ResearchStore, policy: PolicyVersion) -> UUID:
    return store.promote_learning_policy(
        policy_key=policy.policy_key,
        version_label=policy.version_label,
        payload=policy.payload,
        owner_principal_id=policy.owner_principal_id,
        promoted_from_candidate_id=None,
        promotion_reason=policy.promotion_reason,
        evidence=policy.evidence,
    )


def observe_and_persist_terminal_run(store: ResearchStore, run_id: UUID) -> UUID | None:
    """Observe a terminal run and persist learning cases when signals exist."""
    from deepscout_evaluation.learning.observation import observe_from_evaluations
    from deepscout_evaluation.regression_origins import RegressionOrigin

    row = store.get_run_row(run_id)
    if row is None:
        return None
    if row.public_slug:
        return None
    evaluation_rows = store.list_evaluation_results(run_id)
    if not evaluation_rows:
        return None
    case = observe_from_evaluations(
        case_id=f"run-{run_id}",
        evaluation_rows=evaluation_rows,
        config_snapshot=row.config_snapshot,
        research_run_id=run_id,
        owner_principal_id=row.owner_principal_id,
        origin=RegressionOrigin.PRODUCTION_CANDIDATE,
        is_public_demo=bool(row.public_slug),
    )
    case_id: UUID | None = None
    if case is not None:
        existing = store.get_learning_case_by_key(
            case.case_id, owner_principal_id=row.owner_principal_id
        )
        if existing is not None:
            case_id = existing
        else:
            case_id = persist_learning_case(store, case)

    from deepscout_evaluation.learning.monitoring import (
        evaluate_monitoring_rollback,
        record_monitoring_observation,
        run_metrics_from_evaluations,
    )
    from deepscout_evaluation.learning.positive_experience import (
        observe_positive_experience_from_run,
        persist_positive_opportunity,
    )

    consumption = store.get_consumption(run_id)
    metrics = run_metrics_from_evaluations(
        evaluation_rows,
        consumption={
            "tool_calls": consumption.tool_calls,
            "llm_calls": getattr(consumption, "llm_calls", 0),
        }
        if consumption
        else None,
    )
    snapshot = row.config_snapshot or {}
    policy_block = snapshot.get("learning_policies") or {}
    for version in policy_block.get("learning_policy_versions") or []:
        if isinstance(version, dict) and version.get("policy_key"):
            record_monitoring_observation(
                store,
                policy_key=str(version["policy_key"]),
                owner_principal_id=row.owner_principal_id,
                metrics=metrics,
            )
    evaluate_monitoring_rollback(store)

    opportunity = observe_positive_experience_from_run(store, run_id)
    if opportunity is not None:
        persist_positive_opportunity(store, opportunity)

    return case_id


def list_learning_cases_for_owner(
    store: ResearchStore, owner_principal_id: UUID | None
) -> list[dict]:
    return store.list_learning_cases(owner_principal_id=owner_principal_id)


def list_improvement_candidates_for_owner(
    store: ResearchStore, owner_principal_id: UUID | None, *, status: str | None = None
) -> list[dict]:
    return store.list_improvement_candidates(owner_principal_id=owner_principal_id, status=status)
