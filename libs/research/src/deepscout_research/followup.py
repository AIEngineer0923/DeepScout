"""Bounded follow-up context selection. Historical prose is DATA, not authority."""

from __future__ import annotations

import re
from uuid import UUID

from deepscout_persistence.store import ResearchStore

MAX_CLAIMS = 8
MAX_EVIDENCE = 8
MAX_STATEMENTS = 6
MAX_CHARS = 9000


def classify_followup(goal: str) -> str:
    """Classify continuation intent without domain-specific vocabulary."""
    lowered = goal.casefold()
    if re.search(r"\b(?:latest|newer|fresh|recent|updated|oggi|nuov\w*|aggiornat\w*)\b", lowered):
        return "freshness"
    if re.search(r"\b(?:disagree|contradict|conflict|disaccord|contradd|conflitt)\w*\b", lowered):
        return "contradiction"
    if re.search(
        r"\b(?:exclude|remove|without|under budget|maximum|minimum|must include|"
        r"esclud|rimuov|senza|budget|massimo|minimo|includ)\w*\b",
        lowered,
    ):
        return "constraint_change"
    if re.search(r"\b(?:deeper|detail|explain|why|approfond|dettagl|spiega|perche)\w*\b", lowered):
        return "deeper"
    return "continuation"


def _tokens(text: str) -> set[str]:
    return {part for part in text.lower().replace("/", " ").split() if len(part) > 3}


def _score(goal: str, text: str) -> int:
    if not text:
        return 0
    return len(_tokens(goal) & _tokens(text))


def select_followup_context(store: ResearchStore, parent_run_id: UUID, goal: str) -> dict:
    """Pick a bounded, provenance-preserving slice of the parent run."""
    claims = store.list_claims(parent_run_id)
    evidence = store.list_evidence(parent_run_id)
    ranked_claims = sorted(claims, key=lambda row: _score(goal, row.statement), reverse=True)[
        :MAX_CLAIMS
    ]
    claim_ids = {row.id for row in ranked_claims}
    ranked_evidence = [
        row for row in evidence if row.claim_id in claim_ids or _score(goal, row.quote) > 0
    ][:MAX_EVIDENCE]
    report = store.get_report(parent_run_id)
    report_excerpt = ""
    if report is not None:
        report_excerpt = (report.body_markdown or "")[:800]
    wiki_bits: list[str] = []
    try:
        from deepscout_persistence import knowledge as knowledge_store

        statements = knowledge_store.list_statements_for_run(store._session, parent_run_id)
        ranked = sorted(statements, key=lambda row: _score(goal, row.statement_text), reverse=True)[
            :MAX_STATEMENTS
        ]
        wiki_bits = [f"{row.statement_text} [statement:{row.id}]" for row in ranked]
    except Exception:
        wiki_bits = []
    matrix = store.get_entity_research_matrix(parent_run_id) or {}
    ranked_entities_raw = sorted(
        list(matrix.get("entities") or []),
        key=lambda item: (
            _score(goal, str(item.get("entity_name") or ""))
            + max(0, len(item.get("fields") or []) - 1)
        ),
        reverse=True,
    )[:12]
    ranked_entities = [
        {
            "entity_id": item.get("entity_id"),
            "entity_name": item.get("entity_name"),
            "category": item.get("category"),
            "stage": item.get("stage"),
            "fields": [
                {
                    "attribute_key": field.get("attribute_key"),
                    "value": str(field.get("value") or "")[:280],
                    "status": field.get("status"),
                    "evidence_ids": list(field.get("evidence_ids") or [])[:3],
                }
                for field in list(item.get("fields") or [])[:4]
            ],
        }
        for item in ranked_entities_raw
    ]
    parent_row = store.get_run_row(parent_run_id)
    parent_snapshot = dict(parent_row.config_snapshot or {}) if parent_row else {}
    followup_type = classify_followup(goal)
    source_ids: list[str] = []
    for evidence_row in ranked_evidence:
        snapshot = store.get_snapshot(evidence_row.snapshot_id)
        if snapshot is not None and str(snapshot.source_id) not in source_ids:
            source_ids.append(str(snapshot.source_id))
    payload = {
        "parent_run_id": str(parent_run_id),
        "followup_type": followup_type,
        "role": "untrusted_historical_DATA",
        "authority": "Source → SourceSnapshot → Evidence. Report prose is not evidence.",
        "reuse_policy": (
            "Acquire fresh evidence; parent evidence is comparison context only."
            if followup_type == "freshness"
            else "Reuse parent snapshots with provenance, then research only the requested gap."
        ),
        "claims": [
            {
                "id": str(row.id),
                "statement": row.statement[:400],
                "status": row.verification_status.value,
            }
            for row in ranked_claims
        ],
        "evidence": [
            {"id": str(row.id), "claim_id": str(row.claim_id), "quote": row.quote[:280]}
            for row in ranked_evidence
        ],
        "wiki_statements": wiki_bits,
        "report_excerpt": report_excerpt,
        "entity_matrix": {
            "schema_version": matrix.get("schema_version"),
            "entities": ranked_entities,
            "fields_populated": matrix.get("fields_populated", 0),
        },
        "parent_deliverable": (parent_snapshot.get("research_contract") or {}).get(
            "deliverable", {}
        ),
        "parent_deliverable_validation": parent_snapshot.get("deliverable_validation", {}),
        "reusable_source_ids": source_ids[:12],
    }
    encoded = str(payload)
    if len(encoded) > MAX_CHARS:
        payload["report_excerpt"] = payload["report_excerpt"][:400]
        payload["wiki_statements"] = payload["wiki_statements"][:3]
    return payload


def seed_followup_sources(
    store: ResearchStore,
    *,
    parent_run_id: UUID,
    child_run_id: UUID,
    source_ids: list[str],
    limit: int = 12,
) -> int:
    """Copy bounded parent snapshots into a child run with explicit provenance."""
    from deepscout_core.domain.schemas import SourceSnapshotWrite, SourceWrite

    allowed = {item for item in source_ids[:limit]}
    copied = 0
    for source in store.list_sources(parent_run_id):
        if str(source.id) not in allowed:
            continue
        child_source, created = store.add_source(
            child_run_id,
            SourceWrite(
                canonical_url=source.canonical_url,
                title=source.title,
                domain=source.domain,
                source_type=source.source_type,
            ),
        )
        snapshot = store.get_latest_snapshot_for_source(source.id)
        if snapshot is None:
            continue
        metadata = dict(snapshot.retrieval_metadata or {})
        if not metadata.get("original_language"):
            from deepscout_research.language import detect_language

            detected = detect_language(snapshot.content_text)
            metadata.update(
                {
                    "original_language": detected.language,
                    "language_confidence": str(round(detected.confidence, 4)),
                    "language_reason": detected.reason,
                }
            )
        metadata.update(
            {
                "lineage_kind": "followup_reuse",
                "parent_run_id": str(parent_run_id),
                "parent_source_id": str(source.id),
                "parent_snapshot_id": str(snapshot.id),
            }
        )
        store.add_snapshot(
            child_source.id,
            SourceSnapshotWrite(
                content=snapshot.content_text,
                mime_type=snapshot.mime_type,
                retrieval_metadata=metadata,
            ),
        )
        if created:
            copied += 1
    return copied
