"""Secure fetch phase — SourceSnapshot creation."""

from __future__ import annotations

import uuid

from deepscout_core.domain.schemas import SourceSnapshotWrite
from deepscout_persistence.models import SourceRow
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.fetch.secure import SecureFetchError, secure_fetch


@traceable(name="phase:fetch", run_type="chain")
def fetch_sources_for_run(store: ResearchStore, run_id: uuid.UUID, *, max_sources: int = 5) -> int:
    sources = store.list_sources_without_snapshot(run_id, limit=max_sources)
    fetched = 0
    for source in sources:
        try:
            result = secure_fetch(source.canonical_url)
            text = result.body.decode("utf-8", errors="replace")[:500_000]
            store.add_snapshot(
                source.id,
                SourceSnapshotWrite(
                    content=text,
                    mime_type=result.content_type,
                    retrieval_metadata={"final_url": result.url},
                ),
            )
            fetched += 1
        except SecureFetchError:
            continue
    return fetched
