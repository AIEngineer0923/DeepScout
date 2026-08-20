"""Source/evidence extraction — deterministic spans plus structured persistence."""

from __future__ import annotations

import uuid

from deepscout_core.domain.schemas import ClaimWrite, EvidenceWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.phases.text_utils import locate_quote_in_content


@traceable(name="phase:extract", run_type="chain")
def extract_claims_for_run(store: ResearchStore, run_id: uuid.UUID) -> dict[str, int]:
    """Create claims from search snippets and attach evidence when quotes resolve."""
    candidates_by_url = {
        candidate.url: candidate for candidate in store.list_search_candidates(run_id)
    }
    claims_created = 0
    evidence_created = 0

    for source in store.list_sources(run_id):
        snapshot = store.get_latest_snapshot_for_source(source.id)
        if snapshot is None:
            continue
        candidate = candidates_by_url.get(source.canonical_url)
        if candidate is None:
            continue
        statement = candidate.snippet.strip()
        if not statement:
            continue

        claim = store.find_claim(
            run_id,
            source_id=source.id,
            statement=statement,
        )
        if claim is None:
            claim = store.add_claim(
                run_id,
                ClaimWrite(
                    statement=statement[:8000],
                    source_id=source.id,
                    question_id=candidate.question_id,
                ),
            )
            claims_created += 1

        quote = locate_quote_in_content(statement, snapshot.content_text)
        if quote is None:
            continue
        if store.evidence_exists(claim.id, snapshot.id, quote):
            continue
        store.attach_evidence(
            claim.id,
            EvidenceWrite(
                snapshot_id=snapshot.id,
                quote=quote[:16000],
                locator=f"source:{source.canonical_url}",
                support_strength=0.7,
                confidence=0.7,
            ),
        )
        evidence_created += 1

    return {"claims_created": claims_created, "evidence_created": evidence_created}
