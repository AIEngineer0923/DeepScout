"""Operator-only demo publication. Anonymous mutation is never allowed."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import TERMINAL_RESEARCH_RUN_STATUSES
from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.catalog import DEMO_BY_SLUG
from deepscout_research.demo.sanitization import sanitize_text
from sqlalchemy import select


def _sanitize_run_content(store: ResearchStore, run_id: UUID) -> None:
    report = store.get_report(run_id)
    if report is not None:
        report.title = sanitize_text(report.title)
        report.body_markdown = sanitize_text(report.body_markdown)
    for claim in store.list_claims(run_id):
        claim.statement = sanitize_text(claim.statement)
    for item in store.list_evidence(run_id):
        item.quote = sanitize_text(item.quote)


def publish_demo(
    store: ResearchStore,
    run_id: UUID,
    slug: str,
    *,
    require_completed: bool = True,
) -> ResearchRunRow:
    slug = slug.strip().lower().replace(" ", "-")
    if not slug or len(slug) > 80:
        raise ValueError("invalid demo slug")
    row = store.get_run_row(run_id)
    if row is None:
        raise LookupError("run not found")
    if require_completed and row.status not in TERMINAL_RESEARCH_RUN_STATUSES:
        raise ValueError("run must be completed before publication")
    if require_completed and row.status.value != "completed":
        raise ValueError("only completed runs can be published as public demos")
    existing = store._session.scalar(
        select(ResearchRunRow).where(ResearchRunRow.public_slug == slug)
    )
    if existing is not None and existing.id != run_id:
        raise ValueError("slug already published")
    _sanitize_run_content(store, run_id)
    meta = DEMO_BY_SLUG.get(slug)
    if meta:
        store.merge_config_snapshot(
            run_id,
            {
                "public_demo": {
                    "slug": slug,
                    "category": meta["category"],
                    "title": meta["title"],
                    "summary": meta["summary"],
                    "why_interesting": meta["why_interesting"],
                }
            },
        )
    row.is_public_demo = True
    row.public_slug = slug
    store._session.flush()
    return row


def unpublish_demo(store: ResearchStore, run_id: UUID) -> ResearchRunRow:
    row = store.get_run_row(run_id)
    if row is None:
        raise LookupError("run not found")
    row.is_public_demo = False
    row.public_slug = None
    store._session.flush()
    return row
