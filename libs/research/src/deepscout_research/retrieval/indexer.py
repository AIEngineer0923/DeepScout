"""Deterministic snapshot indexing — not an LLM agent."""

from __future__ import annotations

import logging
import uuid

from deepscout_core.domain.enums import AgentRole, IndexingStatus, ResearchPhase, UsageReportStatus
from deepscout_core.domain.usage import TokenUsageRecord
from deepscout_core.settings import Settings
from deepscout_persistence.retrieval import (
    existing_embedding_ids,
    persist_embeddings,
    replace_chunks,
    set_indexing_status,
)
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.retrieval.chunking import chunk_snapshot_text, estimate_tokens
from deepscout_research.retrieval.embeddings import build_embedding_client, embed_documents
from deepscout_research.retrieval.spec import CHUNKING_VERSION, EMBED_BATCH_SIZE, EmbeddingSpec
from deepscout_research.usage.pricing import DEFAULT_PRICING_CATALOG

logger = logging.getLogger(__name__)


@traceable(name="phase:index", run_type="chain")
def index_snapshots_for_run(
    store: ResearchStore,
    settings: Settings,
    run_id: uuid.UUID,
    *,
    client=None,
    spec: EmbeddingSpec | None = None,
) -> dict[str, int]:
    if client is None or spec is None:
        client, spec = build_embedding_client(settings)
    snapshots = store.list_snapshots_for_run(run_id)
    indexed = failed = skipped = 0
    for snapshot in snapshots:
        status = _index_one(store, settings, run_id, snapshot, client=client, spec=spec)
        if status == IndexingStatus.INDEXED:
            indexed += 1
        elif status == IndexingStatus.SKIPPED:
            skipped += 1
        elif status in {IndexingStatus.FAILED, IndexingStatus.PARTIALLY_INDEXED}:
            failed += 1
    return {"indexed": indexed, "failed": failed, "skipped": skipped, "seen": len(snapshots)}


def _index_one(store, settings, run_id, snapshot, *, client, spec: EmbeddingSpec) -> IndexingStatus:
    session = store._session
    if (
        snapshot.indexing_status == IndexingStatus.INDEXED
        and snapshot.embedding_spec_key == spec.key
    ):
        return IndexingStatus.INDEXED
    text = (snapshot.content_text or "").strip()
    if len(text) < 40:
        set_indexing_status(session, snapshot.id, IndexingStatus.SKIPPED, error="empty_or_short")
        return IndexingStatus.SKIPPED
    set_indexing_status(session, snapshot.id, IndexingStatus.INDEXING)
    try:
        drafts = chunk_snapshot_text(snapshot.content_text, snapshot_id=str(snapshot.id))
        rows = replace_chunks(
            session,
            run_id=run_id,
            source_id=snapshot.source_id,
            snapshot_id=snapshot.id,
            chunking_version=CHUNKING_VERSION,
            drafts=[
                {
                    "ordinal": item.ordinal,
                    "text": item.text,
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                    "token_count": item.token_count,
                    "content_hash": item.content_hash,
                    "section_title": item.section_title,
                }
                for item in drafts
            ],
        )
        already = existing_embedding_ids(
            session,
            [row.id for row in rows],
            provider=spec.provider,
            model=spec.model,
            dimensions=spec.dimensions,
            config_version=spec.config_version,
        )
        pending = [row for row in rows if row.id not in already]
        written = 0
        token_total = 0
        for offset in range(0, len(pending), EMBED_BATCH_SIZE):
            batch = pending[offset : offset + EMBED_BATCH_SIZE]
            vectors = embed_documents(client, [row.text for row in batch])
            if len(vectors) != len(batch):
                raise RuntimeError("embedding batch size mismatch")
            persist_embeddings(
                session,
                run_id=run_id,
                provider=spec.provider,
                model=spec.model,
                dimensions=spec.dimensions,
                config_version=spec.config_version,
                items=list(zip([row.id for row in batch], vectors, strict=True)),
            )
            written += len(batch)
            token_total += sum(estimate_tokens(row.text) for row in batch)
        if token_total:
            _record_embedding_usage(store, spec=spec, run_id=run_id, input_tokens=token_total)
        status = (
            IndexingStatus.INDEXED
            if written == len(pending) or not pending
            else IndexingStatus.PARTIALLY_INDEXED
        )
        if pending and written == 0:
            status = IndexingStatus.FAILED
        set_indexing_status(
            session,
            snapshot.id,
            status,
            chunk_count=len(rows),
            embedding_count=len(already) + written,
            chunking_version=CHUNKING_VERSION,
            embedding_spec_key=spec.key,
        )
        return status
    except Exception as exc:
        logger.exception("Indexing failed", extra={"snapshot_id": str(snapshot.id)})
        set_indexing_status(session, snapshot.id, IndexingStatus.FAILED, error=str(exc)[:500])
        return IndexingStatus.FAILED


def _record_embedding_usage(
    store: ResearchStore, *, spec: EmbeddingSpec, run_id: uuid.UUID, input_tokens: int
) -> None:
    usage = TokenUsageRecord(
        research_run_id=run_id,
        phase=ResearchPhase.INDEX,
        agent_role=AgentRole.INDEXER,
        provider=spec.provider,
        model=spec.model,
        input_tokens=input_tokens,
        output_tokens=0,
        total_tokens=input_tokens,
        report_status=UsageReportStatus.PARTIAL,
    )
    catalog = DEFAULT_PRICING_CATALOG
    cost, cost_status = catalog.estimate_cost(usage)
    store.record_token_usage(
        usage,
        pricing_version=catalog.version,
        cost_usd=cost,
        cost_status=cost_status,
    )
