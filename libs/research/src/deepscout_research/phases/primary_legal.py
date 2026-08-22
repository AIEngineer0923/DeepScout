"""Primary legal instrument follow-up fetch after policy guidance discovery."""

from __future__ import annotations

import logging
import uuid

from deepscout_core.domain.schemas import SourceSnapshotWrite, SourceWrite
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.legal_reference import (
    discover_official_links,
    extract_legal_references,
    institutional_profile_url_hints,
    primary_legal_lookup_urls,
)
from deepscout_research.contracts.source_authority import is_source_admissible
from deepscout_research.fetch.content_text import response_to_snapshot_text
from deepscout_research.fetch.secure import SecureFetchError, secure_fetch
from deepscout_research.fetch.url_normalize import normalize_source_url

logger = logging.getLogger(__name__)


def _existing_urls(store: ResearchStore, run_id: uuid.UUID) -> set[str]:
    return {normalize_source_url(source.canonical_url) for source in store.list_sources(run_id)}


def follow_primary_legal_and_profile_urls(
    store: ResearchStore,
    run_id: uuid.UUID,
    *,
    max_additions: int = 4,
) -> dict[str, int]:
    row = store.get_run_row(run_id)
    contract = contract_from_snapshot(row.config_snapshot if row else None)
    prefs = store.list_source_preferences(run_id)
    existing = _existing_urls(store, run_id)
    candidates: list[str] = []
    legal_refs = []

    if contract is not None:
        req_ids = {item.requirement_id for item in contract.requirements}
        if "R_president" in req_ids:
            from deepscout_research.contracts.office_holder import office_title_from_goal

            candidates.extend(
                institutional_profile_url_hints(office_title_from_goal(contract.primary_question))
            )

    for source in store.list_sources(run_id):
        snapshot = store.get_latest_snapshot_for_source(source.id)
        if snapshot is None or not snapshot.content_text.strip():
            continue
        text = snapshot.content_text
        legal_refs.extend(
            extract_legal_references(text, source_url=source.canonical_url)
        )
        candidates.extend(discover_official_links(text, source.canonical_url))

    for ref in legal_refs[:5]:
        candidates.extend(primary_legal_lookup_urls(ref))

    added = 0
    fetched = 0
    for url in list(dict.fromkeys(candidates))[: max_additions * 2]:
        normalized = normalize_source_url(url)
        if normalized in existing:
            continue
        admissible, _ = is_source_admissible(
            normalized,
            contract=contract,
            preferences=prefs,
            title="",
        )
        if not admissible:
            continue
        source, created = store.add_source(
            run_id,
            SourceWrite(
                canonical_url=normalized,
                title=normalized.split("/")[-1][:200] or normalized,
                domain=normalized.split("/")[2] if "://" in normalized else "",
            ),
        )
        existing.add(normalized)
        if not created:
            continue
        added += 1
        try:
            result = secure_fetch(normalized)
            text = response_to_snapshot_text(result.body, result.content_type)[:500_000]
            if len(text.strip()) < 80:
                continue
            store.add_snapshot(
                source.id,
                SourceSnapshotWrite(
                    content=text,
                    mime_type=result.content_type,
                    retrieval_metadata={
                        "final_url": result.url,
                        "extraction_method": "primary_legal_followup",
                    },
                ),
            )
            fetched += 1
        except (SecureFetchError, OSError, TimeoutError) as exc:
            logger.info("Primary legal fetch failed", extra={"url": normalized, "reason": str(exc)[:120]})
        if added >= max_additions:
            break

    if legal_refs:
        store.merge_config_snapshot(
            run_id,
            {
                "legal_references": [ref.model_dump(mode="json") for ref in legal_refs[:10]],
            },
        )
    return {"sources_added": added, "snapshots_fetched": fetched, "legal_refs": len(legal_refs)}
