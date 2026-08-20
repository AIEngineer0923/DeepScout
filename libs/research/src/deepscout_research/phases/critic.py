"""Bounded critic phase — triggered only when validation fails."""

from __future__ import annotations

import uuid

from deepscout_core.domain.schemas import CriticResult
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.prompts import CRITIC_V1, compose_system_message


def _deterministic_critic(store: ResearchStore, run_id: uuid.UUID) -> CriticResult:
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    issues: list[str] = []

    if not claims:
        return CriticResult(
            passed=True,
            artifact_type="research_pipeline",
            severity="pass",
            issues=[],
        )

    evidence_by_claim = {item.claim_id for item in evidence}
    unsupported = [claim for claim in claims if claim.id not in evidence_by_claim]
    if unsupported:
        issues.append(f"{len(unsupported)} claims lack evidence references.")

    for claim in claims:
        if claim.verification_status is None:
            continue
        if claim.verification_status.value in {"verified", "partially_verified"}:
            if claim.id not in evidence_by_claim:
                issues.append(f"Verified claim {claim.id} has no persisted evidence.")

    passed = not issues
    return CriticResult(
        passed=passed,
        artifact_type="research_pipeline",
        severity="pass" if passed else "fail",
        issues=issues[:10],
    )


@traceable(name="phase:critic", run_type="chain", metadata=CRITIC_V1.trace_metadata())
def run_critic_for_run(store: ResearchStore, run_id: uuid.UUID) -> CriticResult:
    """Deterministic critic — LLM critic reserved for synthesis/report failures."""
    _ = compose_system_message(CRITIC_V1)
    return _deterministic_critic(store, run_id)
