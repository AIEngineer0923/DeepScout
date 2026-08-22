"""Durable learning experiment job runner."""

from __future__ import annotations

import logging

from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.experiment import run_experiment

logger = logging.getLogger(__name__)


def process_learning_experiment_jobs(store: ResearchStore, owner: str, *, limit: int = 3) -> int:
    """Run pending deterministic/provider learning experiments off the HTTP path."""
    processed = 0
    for _ in range(limit):
        job = store.claim_learning_experiment_job(owner)
        if job is None:
            break
        candidate_row = store.get_improvement_candidate_row(job.candidate_id)
        if candidate_row is None:
            store.complete_learning_experiment_job(
                job.id, result={"outcome": "failed", "reason": "candidate_missing"}, owner=owner
            )
            processed += 1
            continue
        payload = dict(job.payload or {})
        fixture = payload.get("fixture", {})
        baseline = payload.get("baseline_policy", {})
        from deepscout_evaluation.learning.models import (
            ImprovementCandidate,
            ImprovementCandidateStatus,
            ImprovementCandidateType,
            LearningSubsystem,
            TrustLevel,
        )

        candidate = ImprovementCandidate(
            candidate_id=candidate_row.candidate_key,
            learning_case_id=str(candidate_row.learning_case_id),
            candidate_type=ImprovementCandidateType(candidate_row.candidate_type),
            title=candidate_row.title,
            rationale=candidate_row.rationale or "",
            policy_delta=dict(candidate_row.policy_delta or {}),
            affected_subsystem=LearningSubsystem(candidate_row.affected_subsystem),
            trust_level=TrustLevel(candidate_row.trust_level),
            status=ImprovementCandidateStatus(candidate_row.status),
            owner_principal_id=candidate_row.owner_principal_id,
        )
        experiment = run_experiment(
            case_id=str(candidate.candidate_key),
            baseline_policy=baseline,
            candidate=candidate,
            fixture=fixture,
        )
        store.complete_learning_experiment_job(
            job.id,
            result={
                "outcome": experiment.outcome.value,
                "quality_delta": experiment.quality_delta,
                "cost_delta": experiment.cost_delta,
            },
            owner=owner,
        )
        processed += 1
    return processed
