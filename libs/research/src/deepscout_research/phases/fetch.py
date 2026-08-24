"""Secure fetch phase — SourceSnapshot creation."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from deepscout_core.domain.contracts import AuthorityClass
from deepscout_core.domain.events import ResearchEventType
from deepscout_core.domain.schemas import SourceSnapshotWrite
from deepscout_persistence.models import SourceRow
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.fetch.url_normalize import normalize_source_url
from deepscout_research.source_fabric.acquisition import (
    ContentAcquisitionError,
    ContentAcquisitionRouter,
)
from deepscout_research.source_fabric.registry import baseline_connector_registry

logger = logging.getLogger(__name__)


def _rank_and_diversify_sources(
    store: ResearchStore,
    run_id: uuid.UUID,
    sources: list[SourceRow],
) -> list[SourceRow]:
    """Prefer authoritative/high-relevance sources without starving query coverage."""
    from deepscout_research.contracts.extract import contract_from_snapshot
    from deepscout_research.contracts.source_authority import classify_source_authority
    from deepscout_research.source_fabric.strategy import (
        infer_source_kind,
        plan_source_strategy,
    )

    run = store.get_run(run_id)
    row = store.get_run_row(run_id)
    contract = contract_from_snapshot(row.config_snapshot if row else None)
    strategy = plan_source_strategy(
        run.goal if run else "",
        contract,
        research_mode=run.research_mode if run else None,
    )

    candidates_by_url = defaultdict(list)
    for candidate in store.list_search_candidates(run_id):
        candidates_by_url[normalize_source_url(candidate.url)].append(candidate)

    def _rank(source: SourceRow) -> float:
        authority = classify_source_authority(
            url=source.canonical_url,
            title=source.title or "",
        ).authority_class
        authority_rank = {
            AuthorityClass.PRIMARY: 3,
            AuthorityClass.SECONDARY: 2,
            AuthorityClass.TERTIARY: 1,
            AuthorityClass.UNKNOWN: 0,
        }[authority]
        score = max(
            (
                candidate.score or 0.0
                for candidate in candidates_by_url[normalize_source_url(source.canonical_url)]
            ),
            default=0.0,
        )
        source_kind = infer_source_kind(source.canonical_url, title=source.title or "")
        type_fit = 0.06 if source_kind in strategy.requested_kinds else 0.0
        return score + authority_rank * 0.08 + type_fit

    buckets: dict[str, list[SourceRow]] = defaultdict(list)
    unmatched: list[SourceRow] = []
    for source in sources:
        candidates = candidates_by_url[normalize_source_url(source.canonical_url)]
        if not candidates:
            unmatched.append(source)
            continue
        best = max(candidates, key=lambda candidate: candidate.score or 0.0)
        buckets[best.query].append(source)
    for bucket in buckets.values():
        bucket.sort(key=_rank, reverse=True)

    ordered: list[SourceRow] = []
    while buckets:
        for query in list(buckets):
            bucket = buckets[query]
            ordered.append(bucket.pop(0))
            if not bucket:
                del buckets[query]
    return [*ordered, *sorted(unmatched, key=_rank, reverse=True)]


@traceable(name="phase:fetch", run_type="chain")
def fetch_sources_for_run(store: ResearchStore, run_id: uuid.UUID, *, max_sources: int = 5) -> int:
    # A bounded candidate window lets later sources run when early candidates are unfetchable.
    # ``max_sources`` is a success cap, not an attempt cap.
    sources = store.list_sources_without_snapshot(
        run_id,
        limit=min(50, max(max_sources, max_sources * 5)),
    )
    sources = _rank_and_diversify_sources(store, run_id, sources)
    fetched = 0
    acquisition = ContentAcquisitionRouter(baseline_connector_registry())
    for source in sources:
        if fetched >= max_sources:
            break
        try:
            result = acquisition.acquire(source.canonical_url)
            text = result.text[:500_000]
            if len(text.strip()) < 80:
                logger.info(
                    "Skipping low-value snapshot",
                    extra={"run_id": str(run_id), "url": source.canonical_url},
                )
                continue
            store.add_snapshot(
                source.id,
                SourceSnapshotWrite(
                    content=text,
                    mime_type=result.mime_type,
                    retrieval_metadata=result.metadata,
                ),
            )
            store.append_run_event(
                run_id,
                ResearchEventType.SOURCE_FETCHED.value,
                {
                    "source_id": str(source.id),
                    "source_kind": result.metadata.get("source_kind", "unknown"),
                    "connector": result.metadata.get("connector", "secure_http"),
                    "layer": "tool",
                },
            )
            fetched += 1
        except ContentAcquisitionError as exc:
            logger.info(
                "Fetch skipped for source",
                extra={
                    "run_id": str(run_id),
                    "url": source.canonical_url,
                    "reason": exc.reason.value,
                },
            )
            store.append_run_event(
                run_id,
                ResearchEventType.SOURCE_FETCH_FAILED.value,
                {
                    "source_id": str(source.id),
                    "reason": exc.reason.value,
                    "layer": "tool",
                },
            )
            continue
    return fetched
