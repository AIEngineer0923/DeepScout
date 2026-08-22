"""Structured temporal and office-holder extraction across all admissible snapshots."""

from __future__ import annotations

import uuid

from deepscout_core.domain.schemas import ClaimWrite, EvidenceWrite
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.office_holder import (
    extract_office_holder_evidence,
    office_title_from_goal,
    to_verified_entity,
    verify_office_holder,
)
from deepscout_research.contracts.source_authority import is_source_admissible
from deepscout_research.contracts.temporal_claims import (
    extract_temporal_claims,
    requirement_ids_for_temporal_claim,
)
from deepscout_research.phases.text_utils import locate_quote_in_content


def enrich_structured_evidence(store: ResearchStore, run_id: uuid.UUID) -> dict[str, int]:
    row = store.get_run_row(run_id)
    contract = contract_from_snapshot(row.config_snapshot if row else None)
    goal = row.goal if row else ""
    prefs = store.list_source_preferences(run_id)

    temporal_claims = []
    verified_entities: dict[str, dict] = {}
    claims_created = 0
    evidence_created = 0

    for source in store.list_sources(run_id):
        admissible, _ = is_source_admissible(
            source.canonical_url,
            contract=contract,
            preferences=prefs,
            title=source.title or "",
        )
        if not admissible:
            continue
        snapshot = store.get_latest_snapshot_for_source(source.id)
        if snapshot is None or not snapshot.content_text.strip():
            continue
        text = snapshot.content_text
        url = source.canonical_url

        for claim in extract_temporal_claims(text, source_url=url):
            if not claim.verified:
                continue
            temporal_claims.append(claim.model_dump(mode="json"))
            quote = locate_quote_in_content(claim.evidence_quote, text, min_len=24) or claim.evidence_quote
            req_ids = requirement_ids_for_temporal_claim(claim)
            statement = f"{claim.subject}: {claim.temporal_relation.value} {claim.date_text}"
            claim_row = store.find_claim(run_id, source_id=source.id, statement=statement[:8000])
            if claim_row is None:
                claim_row = store.add_claim(
                    run_id,
                    ClaimWrite(statement=statement[:8000], source_id=source.id),
                )
                claims_created += 1
            if not store.evidence_exists(claim_row.id, snapshot.id, quote):
                store.attach_evidence(
                    claim_row.id,
                    EvidenceWrite(
                        snapshot_id=snapshot.id,
                        quote=quote[:16000],
                        locator=f"temporal:{url}",
                        support_strength=0.9,
                        confidence=0.9,
                        extraction_metadata={
                            "requirement_ids": req_ids,
                            "temporal_relation": claim.temporal_relation.value,
                            "date_text": claim.date_text,
                            "structured": True,
                        },
                    ),
                )
                evidence_created += 1

        office = extract_office_holder_evidence(
            text,
            source_url=url,
            office_title=office_title_from_goal(goal),
        )
        if office and verify_office_holder(office):
            quote = locate_quote_in_content(office.evidence_span, text, min_len=24) or office.evidence_span
            statement = f"{office.person_name} — {office.office_title}"
            claim_row = store.find_claim(run_id, source_id=source.id, statement=statement[:8000])
            if claim_row is None:
                claim_row = store.add_claim(
                    run_id,
                    ClaimWrite(statement=statement[:8000], source_id=source.id),
                )
                claims_created += 1
            if not store.evidence_exists(claim_row.id, snapshot.id, quote):
                ev = store.attach_evidence(
                    claim_row.id,
                    EvidenceWrite(
                        snapshot_id=snapshot.id,
                        quote=quote[:16000],
                        locator=f"office-holder:{url}",
                        support_strength=0.95,
                        confidence=0.95,
                        extraction_metadata={
                            "requirement_ids": ["R_president"],
                            "office_holder_name": office.person_name,
                            "structured": True,
                        },
                    ),
                )
                evidence_created += 1
                verified_entities["entity-office-holder"] = to_verified_entity(
                    office,
                    task_key="entity-office-holder",
                    evidence_id=str(ev.id),
                ).model_dump(mode="json")

    merge_payload: dict = {}
    if temporal_claims:
        merge_payload["temporal_claims"] = temporal_claims[:30]
    if verified_entities:
        merge_payload["verified_entities"] = verified_entities
    if merge_payload:
        store.merge_config_snapshot(run_id, merge_payload)

    return {
        "temporal_claims": len(temporal_claims),
        "verified_entities": len(verified_entities),
        "claims_created": claims_created,
        "evidence_created": evidence_created,
    }
