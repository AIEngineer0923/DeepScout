"""Bounded follow-up context selection. Historical prose is DATA, not authority."""

from __future__ import annotations

from uuid import UUID

from deepscout_persistence.store import ResearchStore

MAX_CLAIMS = 8
MAX_EVIDENCE = 8
MAX_STATEMENTS = 6
MAX_CHARS = 3500


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
    ranked_claims = sorted(
        claims, key=lambda row: _score(goal, row.statement), reverse=True
    )[:MAX_CLAIMS]
    claim_ids = {row.id for row in ranked_claims}
    ranked_evidence = [
        row
        for row in evidence
        if row.claim_id in claim_ids or _score(goal, row.quote) > 0
    ][:MAX_EVIDENCE]
    report = store.get_report(parent_run_id)
    report_excerpt = ""
    if report is not None:
        report_excerpt = (report.body_markdown or "")[:800]
    wiki_bits: list[str] = []
    try:
        from deepscout_persistence import knowledge as knowledge_store

        statements = knowledge_store.list_statements_for_run(store._session, parent_run_id)
        ranked = sorted(
            statements, key=lambda row: _score(goal, row.statement_text), reverse=True
        )[:MAX_STATEMENTS]
        wiki_bits = [f"{row.statement_text} [statement:{row.id}]" for row in ranked]
    except Exception:
        wiki_bits = []
    payload = {
        "parent_run_id": str(parent_run_id),
        "role": "untrusted_historical_DATA",
        "authority": "Source → SourceSnapshot → Evidence. Report prose is not evidence.",
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
    }
    encoded = str(payload)
    if len(encoded) > MAX_CHARS:
        payload["report_excerpt"] = payload["report_excerpt"][:400]
        payload["wiki_statements"] = payload["wiki_statements"][:3]
    return payload
