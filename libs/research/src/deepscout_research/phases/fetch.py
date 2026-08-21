"""Secure fetch phase — SourceSnapshot creation."""

from __future__ import annotations

import logging
import uuid

from deepscout_core.domain.schemas import SourceSnapshotWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.fetch.content_text import response_to_snapshot_text
from deepscout_research.fetch.secure import SecureFetchError, secure_fetch

logger = logging.getLogger(__name__)


@traceable(name="phase:fetch", run_type="chain")
def fetch_sources_for_run(store: ResearchStore, run_id: uuid.UUID, *, max_sources: int = 5) -> int:
    sources = store.list_sources_without_snapshot(run_id, limit=max_sources)
    fetched = 0
    for source in sources:
        try:
            result = secure_fetch(source.canonical_url)
            text = response_to_snapshot_text(result.body, result.content_type)[:500_000]
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
                    mime_type=result.content_type,
                    retrieval_metadata={
                        "final_url": result.url,
                        "extraction_method": "deterministic_visible_text",
                        "raw_bytes": str(len(result.body)),
                    },
                ),
            )
            fetched += 1
        except (SecureFetchError, OSError, TimeoutError) as exc:
            logger.info(
                "Fetch skipped for source",
                extra={
                    "run_id": str(run_id),
                    "url": source.canonical_url,
                    "reason": str(exc)[:200],
                },
            )
            continue
    return fetched
