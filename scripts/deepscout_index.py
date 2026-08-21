#!/usr/bin/env python3
"""Backfill snapshot indexing for local development — not run by Alembic."""

from __future__ import annotations

import argparse
import sys
import uuid

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.retrieval.enabled import retrieval_enabled
from deepscout_research.retrieval.indexer import index_snapshots_for_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index SourceSnapshots for retrieval")
    parser.add_argument("run_id", help="Research run UUID")
    args = parser.parse_args(argv)
    settings = get_settings()
    if not retrieval_enabled(settings):
        print(
            "Embedding provider is not configured; set GOOGLE_API_KEY or OPENAI_API_KEY",
            file=sys.stderr,
        )
        return 2
    run_id = uuid.UUID(args.run_id)
    session_factory = get_session_factory(settings.database_url)
    with session_factory() as session:
        store = ResearchStore(session)
        run = store.get_run(run_id)
        if run is None:
            print(f"Run {run_id} not found", file=sys.stderr)
            return 1
        stats = index_snapshots_for_run(store, settings, run_id)
        store.commit()
        print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
