"""Operator-only demo publication. Anonymous mutation is never allowed."""

from __future__ import annotations

from uuid import UUID

from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.store import ResearchStore
from sqlalchemy import select


def publish_demo(store: ResearchStore, run_id: UUID, slug: str) -> ResearchRunRow:
    slug = slug.strip().lower().replace(" ", "-")
    if not slug or len(slug) > 80:
        raise ValueError("invalid demo slug")
    row = store.get_run_row(run_id)
    if row is None:
        raise LookupError("run not found")
    existing = store._session.scalar(
        select(ResearchRunRow).where(ResearchRunRow.public_slug == slug)
    )
    if existing is not None and existing.id != run_id:
        raise ValueError("slug already published")
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
