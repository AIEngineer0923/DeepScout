"""Claim verification — deterministic quote checks plus status transitions."""

from __future__ import annotations

import uuid

from deepscout_core.domain.enums import ClaimVerificationStatus
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.source_authority import is_source_admissible
from deepscout_research.phases.text_utils import locate_quote_in_content


@traceable(name="phase:verify", run_type="chain")
def verify_claims_for_run(store: ResearchStore, run_id: uuid.UUID) -> dict[str, int]:
    verified = 0
    partial = 0
    refuted = 0
    insufficient = 0
    rejected_policy = 0

    row = store.get_run_row(run_id)
    contract = contract_from_snapshot(row.config_snapshot if row else None)
    prefs = store.list_source_preferences(run_id)
    sources_by_id = {source.id: source for source in store.list_sources(run_id)}

    for claim in store.list_claims(run_id):
        source = sources_by_id.get(claim.source_id) if claim.source_id else None
        if source is not None:
            admissible, _ = is_source_admissible(
                source.canonical_url,
                contract=contract,
                preferences=prefs,
                title=source.title or "",
            )
            if not admissible:
                store.update_claim_verification(
                    claim.id,
                    ClaimVerificationStatus.INSUFFICIENT_EVIDENCE,
                )
                rejected_policy += 1
                continue

        evidence_items = store.list_evidence_for_claim(claim.id)
        if not evidence_items:
            store.update_claim_verification(claim.id, ClaimVerificationStatus.INSUFFICIENT_EVIDENCE)
            insufficient += 1
            continue

        matches = 0
        for item in evidence_items:
            snapshot = store.get_snapshot(item.snapshot_id)
            if snapshot is None:
                continue
            if locate_quote_in_content(item.quote, snapshot.content_text, min_len=8):
                matches += 1

        if matches == len(evidence_items):
            store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)
            verified += 1
        elif matches > 0:
            store.update_claim_verification(claim.id, ClaimVerificationStatus.PARTIALLY_VERIFIED)
            partial += 1
        else:
            store.update_claim_verification(claim.id, ClaimVerificationStatus.REFUTED)
            refuted += 1

    return {
        "verified": verified,
        "partially_verified": partial,
        "refuted": refuted,
        "insufficient_evidence": insufficient,
        "rejected_policy": rejected_policy,
    }
