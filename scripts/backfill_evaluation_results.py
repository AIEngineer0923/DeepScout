#!/usr/bin/env python3
"""Bounded deterministic evaluation backfill for terminal research runs."""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from deepscout_core.domain.enums import TERMINAL_RESEARCH_RUN_STATUSES
from deepscout_core.settings import Settings
from deepscout_evaluation.persist import persist_research_evaluations
from deepscout_persistence.models import EvaluationResultRow, ResearchRunRow
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from sqlalchemy import exists, select


def _terminal_runs_missing_evaluations(
    session,
    *,
    limit: int,
    public_demo_only: bool,
    run_ids: list[UUID] | None,
) -> list[UUID]:
    has_eval = exists().where(EvaluationResultRow.research_run_id == ResearchRunRow.id)
    stmt = (
        select(ResearchRunRow.id)
        .where(ResearchRunRow.status.in_(tuple(TERMINAL_RESEARCH_RUN_STATUSES)))
        .where(~has_eval)
        .order_by(ResearchRunRow.updated_at.desc())
    )
    if public_demo_only:
        stmt = stmt.where(ResearchRunRow.public_slug.is_not(None))
    if run_ids:
        stmt = stmt.where(ResearchRunRow.id.in_(run_ids))
    stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report candidates without writing")
    parser.add_argument("--limit", type=int, default=100, help="Max terminal runs to process")
    parser.add_argument(
        "--public-demo-only",
        action="store_true",
        help="Only backfill published demo runs (public_slug set)",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=[],
        help="Restrict to specific run UUID (repeatable)",
    )
    args = parser.parse_args()

    settings = Settings()
    session = get_session_factory(settings.database_url)()
    run_ids = [UUID(value) for value in args.run_id] or None
    candidates = _terminal_runs_missing_evaluations(
        session,
        limit=args.limit,
        public_demo_only=args.public_demo_only,
        run_ids=run_ids,
    )
    session.close()

    report = {
        "dry_run": args.dry_run,
        "runs_scanned": len(candidates),
        "runs_updated": 0,
        "rows_inserted": 0,
        "rows_skipped": 0,
        "errors": [],
        "provider_calls": 0,
    }

    if args.dry_run or not candidates:
        print(json.dumps(report, indent=2))
        return 0

    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    try:
        for run_id in candidates:
            before = len(store.list_evaluation_results(run_id))
            if before:
                report["rows_skipped"] += before
                continue
            try:
                rows = persist_research_evaluations(store, run_id)
                session.commit()
                report["runs_updated"] += 1
                report["rows_inserted"] += len(rows)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                report["errors"].append({"run_id": str(run_id), "error": str(exc)})
    finally:
        session.close()

    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
