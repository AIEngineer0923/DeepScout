"""Source/evidence extraction from real SourceSnapshot text."""

from __future__ import annotations

import re
import uuid

from deepscout_core.domain.enums import AgentRole
from deepscout_core.domain.schemas import ClaimWrite, EvidenceWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.fetch.content_text import split_sentences
from deepscout_research.fetch.url_normalize import normalize_source_url
from deepscout_research.phases.text_utils import locate_quote_in_content
from deepscout_research.retrieval.chunking import estimate_tokens
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.service import RetrievalService


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
    specialized = _select_specialized_sentence(snapshot_text, query=query)
    if specialized is not None:
        return specialized
    best: tuple[int, str] | None = None
    for sentence in split_sentences(snapshot_text):
        score = _score_sentence(sentence, query=query, hint=hint)
        if score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, sentence)
    return best[1] if best else None


def _select_specialized_sentence(snapshot_text: str, *, query: str) -> str | None:
    lowered_query = query.casefold()
    if any(token in lowered_query for token in ("president", "presidente", "office-holder", "leadership")):
        for sentence in split_sentences(snapshot_text):
            lowered = sentence.casefold()
            if ("president" not in lowered and "presidente" not in lowered) or (
                "commission" not in lowered and "commissione" not in lowered
            ):
                continue
            if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z'-]+){1,3}\b", sentence):
                return sentence
    if any(
        token in lowered_query
        for token in ("applicable", "transitional", "timeline", "enforcement", "gpai", "article", "vigore")
    ):
        for sentence in split_sentences(snapshot_text):
            if not re.search(r"\b20\d{2}\b", sentence):
                continue
            lowered = sentence.casefold()
            if any(
                token in lowered
                for token in (
                    "applic",
                    "vigore",
                    "transitional",
                    "successiv",
                    "enforcement",
                    "article",
                    "entered into force",
                    "entra in vigore",
                )
            ):
                return sentence
    return None


@traceable(name="phase:extract", run_type="chain")
def extract_claims_for_run(
    store: ResearchStore,
    run_id: uuid.UUID,
    *,
    retriever: RetrievalService | None = None,
) -> dict[str, int]:
    """Create claims and evidence only from verifiable SourceSnapshot text."""
    candidates_by_url = {
        normalize_source_url(candidate.url): candidate
        for candidate in store.list_search_candidates(run_id)
    }
    claims_created = 0
    evidence_created = 0
    retrieved_used = 0
    row = store.get_run_row(run_id)
    from deepscout_research.contracts.extract import contract_from_snapshot
    from deepscout_research.contracts.evidence_relevance import is_evidence_relevant
    from deepscout_research.contracts.source_authority import is_source_admissible

    contract = contract_from_snapshot(row.config_snapshot if row else None)
    goal = row.goal if row else ""
    prefs = store.list_source_preferences(run_id)

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
        candidate = candidates_by_url.get(normalize_source_url(source.canonical_url))
        query = candidate.query if candidate is not None else goal[:500]
        hint = candidate.snippet if candidate is not None else (source.title or "")
        if not query.strip():
            continue

        search_text = snapshot.content_text
        if retriever is not None and candidate is not None:
            from deepscout_research.preferences.snapshot import preferences_from_snapshot

            row = store.get_run_row(run_id)
            resolved = preferences_from_snapshot(
                row.config_snapshot if row else None,
                goal=row.goal if row else "",
            )
            plan = plan_retrieval_query(
                query=candidate.query,
                run_id=run_id,
                settings=retriever.settings,
                source_ids=[source.id],
                role=AgentRole.EXTRACTOR,
                document_token_estimate=estimate_tokens(snapshot.content_text),
                fresher_than=resolved.fresher_than,
            )
            if not plan.skip_retrieval:
                hits = retriever.retrieve(
                    RetrievalQuery(
                        query=plan.semantic_query,
                        run_id=run_id,
                        source_ids=plan.source_ids,
                        top_k=plan.top_k,
                        candidate_k=plan.candidate_k,
                        mode=plan.mode,
                        fresher_than=plan.fresher_than,
                    )
                )
                if hits:
                    retrieved_used += 1
                    search_text = "\n".join(item.text for item in hits)

        statement = _select_snapshot_sentence(
            search_text,
            query=query,
            hint=hint,
        )
        if statement is None:
            continue
        quote = locate_quote_in_content(statement, snapshot.content_text, min_len=24)
        if quote is None:
            continue
        if not is_evidence_relevant(
            quote=quote,
            query=query,
            goal=goal,
            contract=contract,
        ):
            continue

        from deepscout_research.contracts.requirement_attribution import attribute_requirements

        requirement_ids = (
            attribute_requirements(statement=quote[:8000], quote=quote, contract=contract)
            if contract
            else []
        )

        claim = store.find_claim(
            run_id,
            source_id=source.id,
            statement=quote[:8000],
        )
        if claim is None:
            claim = store.add_claim(
                run_id,
                ClaimWrite(
                    statement=quote[:8000],
                    source_id=source.id,
                    question_id=candidate.question_id if candidate is not None else None,
                ),
            )
            claims_created += 1

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
                extraction_metadata={"requirement_ids": requirement_ids},
            ),
        )
        evidence_created += 1

    return {
        "claims_created": claims_created,
        "evidence_created": evidence_created,
        "retrieved_sources": retrieved_used,
    }
