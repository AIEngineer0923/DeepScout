"""Source/evidence extraction from real SourceSnapshot text."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict

from deepscout_core.domain.enums import AgentRole
from deepscout_core.domain.schemas import ClaimWrite, EvidenceWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.contracts.text_normalize import normalized_research_tokens
from deepscout_research.fetch.content_text import split_sentences
from deepscout_research.fetch.url_normalize import normalize_source_url
from deepscout_research.phases.claim_candidate import claim_candidate_rejection, is_claim_candidate
from deepscout_research.phases.text_utils import locate_quote_in_content
from deepscout_research.retrieval.chunking import estimate_tokens
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.service import RetrievalService


def _keyword_tokens(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        tokens.update(normalized_research_tokens(part))
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
        if not is_claim_candidate(sentence):
            continue
        score = _score_sentence(sentence, query=query, hint=hint)
        if score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, sentence)
    return best[1] if best else None


def _select_snapshot_sentences(
    snapshot_text: str,
    *,
    query: str,
    hint: str,
    limit: int,
    min_score: int = 2,
) -> list[str]:
    """Select a small, diverse evidence set instead of one sentence per source."""
    ranked: list[tuple[int, int, str]] = []
    specialized = _select_specialized_sentence(snapshot_text, query=query)
    for index, sentence in enumerate(split_sentences(snapshot_text)):
        # Navigation bars and headlines are dense in topical nouns, so keyword
        # overlap alone ranks them highly. Shape has to be checked first.
        if not is_claim_candidate(sentence):
            continue
        score = _score_sentence(sentence, query=query, hint=hint)
        if score >= min_score:
            ranked.append((score, -index, sentence))
    selected = [item[2] for item in sorted(ranked, reverse=True)]
    if specialized is not None:
        selected.insert(0, specialized)
    return list(dict.fromkeys(selected))[: max(1, limit)]


def _select_specialized_sentence(snapshot_text: str, *, query: str) -> str | None:
    lowered_query = query.casefold()
    if any(
        token in lowered_query
        for token in ("president", "presidente", "office-holder", "leadership")
    ):
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
        for token in (
            "applicable",
            "transitional",
            "timeline",
            "enforcement",
            "gpai",
            "article",
            "vigore",
        )
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
    search_candidates = store.list_search_candidates(run_id)
    claims_created = 0
    evidence_created = 0
    retrieved_used = 0
    row = store.get_run_row(run_id)
    from deepscout_research.contracts.evidence_relevance import (
        is_evidence_relevant,
        planned_query_language,
    )
    from deepscout_research.contracts.extract import contract_from_snapshot
    from deepscout_research.contracts.source_authority import is_source_admissible

    contract = contract_from_snapshot(row.config_snapshot if row else None)
    goal = row.goal if row else ""
    prefs = store.list_source_preferences(run_id)
    from deepscout_research.contracts.requirement_attribution import requirements_for_query
    from deepscout_research.language import language_execution_summary, normalize_language_tag

    language_query_provenance = {
        " ".join(item.query.casefold().split()): item
        for item in (contract.language_strategy.query_variants if contract else [])
    }

    candidates_by_url: dict[str, list] = defaultdict(list)
    for candidate in search_candidates:
        key = normalize_source_url(candidate.url)
        candidates_by_url[key].append(candidate)

    def _candidate_rank(item) -> tuple[int, float]:
        provenance = requirements_for_query(query=item.query, contract=contract) if contract else []
        return (int(len(provenance) == 1), item.score or 0.0)

    for key, items in candidates_by_url.items():
        unique: list = []
        seen_queries: set[str] = set()
        for item in sorted(items, key=_candidate_rank, reverse=True):
            normalized_query = " ".join(item.query.casefold().split())
            if normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)
            unique.append(item)
        # One URL often serves several entities/attributes. Keeping a bounded
        # set of distinct query provenances fixes the former one-query-per-URL
        # bottleneck without multiplying network acquisition.
        candidates_by_url[key] = unique[:6]

    rejection_counts: Counter[str] = Counter()
    rejection_samples: list[dict] = []
    evidence_candidates = 0
    retrieved_chunks = 0
    admitted_sources = 0
    fetched_sources = 0

    def reject(reason: str, *, source_id: uuid.UUID, detail: str = "") -> None:
        rejection_counts[reason] += 1
        if len(rejection_samples) < 50:
            rejection_samples.append(
                {"reason": reason, "source_id": str(source_id), "detail": detail[:300]}
            )

    for source in store.list_sources(run_id):
        admissible, _ = is_source_admissible(
            source.canonical_url,
            contract=contract,
            preferences=prefs,
            title=source.title or "",
        )
        if not admissible:
            reject("source_type_mismatch", source_id=source.id)
            continue
        admitted_sources += 1
        snapshot = store.get_latest_snapshot_for_source(source.id)
        if snapshot is None or not snapshot.content_text.strip():
            reject("content_missing", source_id=source.id)
            continue
        fetched_sources += 1
        candidates = candidates_by_url.get(normalize_source_url(source.canonical_url)) or [None]
        for candidate in candidates:
            raw_query = candidate.query if candidate is not None else goal[:500]
            planned_variant = language_query_provenance.get(" ".join(raw_query.casefold().split()))
            valid_requirement_ids = {
                item.requirement_id for item in (contract.requirements if contract else [])
            }
            provenance_ids = (
                [item for item in planned_variant.requirement_ids if item in valid_requirement_ids]
                if planned_variant
                else []
            )
            if contract and not provenance_ids:
                provenance_ids = requirements_for_query(query=raw_query, contract=contract)
            provenance_requirements = [
                item
                for item in (contract.requirements if contract else [])
                if item.requirement_id in provenance_ids
            ]
            # Attribute-aware extraction searches against the requested field,
            # while retaining the original query for provenance.
            query = (
                raw_query
                if planned_variant is not None
                else " ".join(item.text for item in provenance_requirements[:2])[:1000]
                if provenance_requirements
                else raw_query
            )
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
                top_k_override, candidate_k_override = None, None
                try:
                    from deepscout_evaluation.learning.policy_runtime import (
                        retrieval_overrides_from_snapshot,
                    )

                    top_k_override, candidate_k_override = retrieval_overrides_from_snapshot(
                        row.config_snapshot if row else None,
                        retriever.settings,
                    )
                except Exception:
                    pass
                plan = plan_retrieval_query(
                    query=query,
                    run_id=run_id,
                    settings=retriever.settings,
                    source_ids=[source.id],
                    role=AgentRole.EXTRACTOR,
                    document_token_estimate=estimate_tokens(snapshot.content_text),
                    fresher_than=resolved.fresher_than,
                    retrieval_top_k_override=top_k_override,
                    retrieval_candidate_k_override=candidate_k_override,
                )
                if not plan.skip_retrieval:
                    mode = (
                        row.research_mode
                        if row and row.research_mode in {"quick", "standard", "deep"}
                        else "standard"
                    )
                    hits = retriever.retrieve(
                        RetrievalQuery(
                            query=plan.semantic_query,
                            run_id=run_id,
                            source_ids=plan.source_ids,
                            top_k=plan.top_k,
                            candidate_k=plan.candidate_k,
                            mode=plan.mode,
                            corpus=plan.corpus,
                            fresher_than=plan.fresher_than,
                            research_mode=mode,  # type: ignore[arg-type]
                        )
                    )
                    if hits:
                        from deepscout_research.retrieval.context import assemble_context

                        packed = assemble_context(
                            [item for item in hits if item.provenance_kind == "chunk"]
                        )
                        if not packed:
                            packed = hits
                        retrieved_used += 1
                        retrieved_chunks += len(packed)
                        search_text = "\n".join(item.text for item in packed)

            research_mode = (
                row.research_mode
                if row and row.research_mode in {"quick", "standard", "deep"}
                else "standard"
            )
            for sentence in split_sentences(search_text):
                reason = claim_candidate_rejection(sentence)
                if reason is not None:
                    rejection_counts[f"shape:{reason}"] += 1
            statements = _select_snapshot_sentences(
                search_text,
                query=query,
                hint=hint,
                limit={"quick": 2, "standard": 4, "deep": 6}[research_mode],
                min_score=1 if provenance_requirements else 2,
            )
            if not statements:
                reject("insufficient_specificity", source_id=source.id, detail=query)
                continue
            evidence_candidates += len(statements)
            for statement in statements:
                quote = locate_quote_in_content(statement, snapshot.content_text, min_len=24)
                if quote is None:
                    reject("quote_not_resolved", source_id=source.id, detail=statement)
                    continue
                if not is_evidence_relevant(
                    quote=quote,
                    query=query,
                    goal=goal,
                    contract=contract,
                    requirement=provenance_requirements[0]
                    if len(provenance_requirements) == 1
                    else None,
                    min_score=1 if provenance_requirements else 2,
                ):
                    reject("irrelevant", source_id=source.id, detail=quote)
                    continue

                from deepscout_research.contracts.evidence_types import classify_evidence_type
                from deepscout_research.contracts.requirement_attribution import (
                    attribute_requirements,
                )
                from deepscout_research.contracts.source_authority import (
                    classify_source_authority,
                )

                requirement_ids = (
                    attribute_requirements(statement=quote[:8000], quote=quote, contract=contract)
                    if contract
                    else []
                )
                if contract:
                    requirement_ids = list(dict.fromkeys([*requirement_ids, *provenance_ids]))[:10]
                authority = classify_source_authority(
                    url=source.canonical_url,
                    title=source.title or "",
                )
                evidence_type = classify_evidence_type(
                    source=authority,
                    title=source.title or "",
                    text=quote,
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
                    store.merge_evidence_metadata(
                        claim.id,
                        snapshot.id,
                        quote,
                        {
                            "requirement_ids": requirement_ids,
                            "evidence_type": evidence_type.value,
                            "source_class": authority.source_class.value,
                            "original_language": normalize_language_tag(
                                (snapshot.retrieval_metadata or {}).get("original_language")
                            ),
                            "translation_state": "original",
                        },
                    )
                    reject("duplicate", source_id=source.id, detail=quote)
                    continue
                store.attach_evidence(
                    claim.id,
                    EvidenceWrite(
                        snapshot_id=snapshot.id,
                        quote=quote[:16000],
                        locator=f"source:{source.canonical_url}",
                        support_strength=0.8,
                        confidence=0.8,
                        extraction_metadata={
                            "requirement_ids": requirement_ids,
                            "evidence_type": evidence_type.value,
                            "source_class": authority.source_class.value,
                            "extraction_query": raw_query[:500],
                            "query_language": (
                                normalize_language_tag(planned_variant.language)
                                if planned_variant
                                else planned_query_language(raw_query, contract)
                            ),
                            "original_language": normalize_language_tag(
                                (snapshot.retrieval_metadata or {}).get("original_language")
                            ),
                            "original_source": source.canonical_url,
                            "original_locator": f"source:{source.canonical_url}",
                            "translation_state": "original",
                            "attribute_keys": [
                                item.attribute_key
                                for item in (
                                    contract.deliverable.attribute_goals if contract else []
                                )
                                if set(item.requirement_ids) & set(requirement_ids)
                            ][:8],
                        },
                    ),
                )
                evidence_created += 1

    snapshots = store.list_snapshots_for_run(run_id)
    metrics = {
        "candidate_sources": len(search_candidates),
        "candidate_urls": len(candidates_by_url),
        "discovered_sources": len(store.list_sources(run_id)),
        "admitted_sources": admitted_sources,
        "fetched_sources": fetched_sources,
        "snapshots": len(snapshots),
        "chunks": sum(item.chunk_count for item in snapshots),
        "retrieved_chunks": retrieved_chunks,
        "evidence_candidates": evidence_candidates,
        "evidence_admitted": len(store.list_evidence(run_id)),
        "evidence_rejected": sum(rejection_counts.values()),
        "claims": len(store.list_claims(run_id)),
        "matrix_fields_populated": 0,
    }
    store.upsert_research_funnel(
        run_id,
        metrics=metrics,
        rejection_counts=dict(rejection_counts),
        rejection_samples=rejection_samples,
    )
    store.merge_config_snapshot(
        run_id,
        {"language_execution": language_execution_summary(store, run_id, contract=contract)},
    )

    return {
        "claims_created": claims_created,
        "evidence_created": evidence_created,
        "retrieved_sources": retrieved_used,
        "retrieved_chunks": retrieved_chunks,
        "evidence_candidates": evidence_candidates,
        "evidence_rejected": sum(rejection_counts.values()),
    }
