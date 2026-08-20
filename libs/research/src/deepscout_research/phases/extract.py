"""Source/evidence extraction from real SourceSnapshot text."""

from __future__ import annotations

import re
import uuid

from deepscout_core.domain.schemas import ClaimWrite, EvidenceWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.fetch.content_text import split_sentences
from deepscout_research.fetch.url_normalize import normalize_source_url
from deepscout_research.phases.text_utils import locate_quote_in_content


def _keyword_tokens(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in re.findall(r"[a-z0-9]{3,}", part.lower()):
            tokens.add(token)
    return tokens


def _score_sentence(sentence: str, *, query: str, hint: str) -> int:
    sentence_tokens = _keyword_tokens(sentence)
    target_tokens = _keyword_tokens(query, hint)
    if not target_tokens:
        return 0
    return len(sentence_tokens & target_tokens)


def _select_snapshot_sentence(
    snapshot_text: str,
    *,
    query: str,
    hint: str,
    min_score: int = 2,
) -> str | None:
    best: tuple[int, str] | None = None
    for sentence in split_sentences(snapshot_text):
        score = _score_sentence(sentence, query=query, hint=hint)
        if score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, sentence)
    return best[1] if best else None


@traceable(name="phase:extract", run_type="chain")
def extract_claims_for_run(store: ResearchStore, run_id: uuid.UUID) -> dict[str, int]:
    """Create claims and evidence only from verifiable SourceSnapshot text."""
    candidates_by_url = {
        normalize_source_url(candidate.url): candidate
        for candidate in store.list_search_candidates(run_id)
    }
    claims_created = 0
    evidence_created = 0

    for source in store.list_sources(run_id):
        snapshot = store.get_latest_snapshot_for_source(source.id)
        if snapshot is None or not snapshot.content_text.strip():
            continue
        candidate = candidates_by_url.get(normalize_source_url(source.canonical_url))
        if candidate is None:
            continue

        statement = _select_snapshot_sentence(
            snapshot.content_text,
            query=candidate.query,
            hint=candidate.snippet,
        )
        if statement is None:
            continue
        if statement not in snapshot.content_text:
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

        quote = locate_quote_in_content(statement, snapshot.content_text, min_len=24)
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
                support_strength=0.8,
                confidence=0.8,
            ),
        )
        evidence_created += 1

    return {"claims_created": claims_created, "evidence_created": evidence_created}
