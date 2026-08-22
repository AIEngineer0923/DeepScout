"""Operator-only demo publication. Anonymous mutation is never allowed."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import TERMINAL_RESEARCH_RUN_STATUSES
from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.store import ResearchStore
from sqlalchemy import select

from deepscout_research.demo.catalog import DEMO_BY_SLUG
from deepscout_research.demo.presentation import merge_presentation_into_public_demo
from deepscout_research.demo.presentation_validation import (
    resolve_publication_presentations,
    validate_demo_presentation_locales,
)
from deepscout_research.demo.sanitization import sanitize_text


def _sanitize_run_content(store: ResearchStore, run_id: UUID) -> None:
    report = store.get_report(run_id)
    if report is not None:
        report.title = sanitize_text(report.title)
        report.body_markdown = sanitize_text(report.body_markdown)
    for claim in store.list_claims(run_id):
        claim.statement = sanitize_text(claim.statement)
    for item in store.list_evidence(run_id):
        item.quote = sanitize_text(item.quote)


def _presentation_reason_codes(store: ResearchStore, run_id: UUID, slug: str) -> list[str]:
    row = store.get_run_row(run_id)
    if row is None:
        return ["PRESENTATION_SCHEMA_INVALID"]
    snapshot = row.config_snapshot or {}
    tasks = store.list_tasks(run_id)
    claims = store.list_claims(run_id)
    presentations = resolve_publication_presentations(snapshot, slug)
    return validate_demo_presentation_locales(
        presentations,
        run_task_keys={task.task_key for task in tasks if task.task_key},
        run_worker_ids={str(task.worker_id) for task in tasks if task.worker_id},
        run_claim_ids={str(claim.id) for claim in claims},
        expected_run_id=run_id,
    )


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
    presentation_errors = _presentation_reason_codes(store, run_id, slug)
    if presentation_errors:
        raise ValueError("; ".join(presentation_errors))
    _sanitize_run_content(store, run_id)
    meta = DEMO_BY_SLUG.get(slug)
    if meta:
        public_demo = merge_presentation_into_public_demo(
            {
                "slug": slug,
                "category": meta["category"],
                "title": meta["title"],
                "summary": meta["summary"],
                "why_interesting": meta["why_interesting"],
            },
            slug,
        )
        store.merge_config_snapshot(run_id, {"public_demo": public_demo})
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
