"""Public demo catalog — always read-only, no auth required on hosted."""

from __future__ import annotations

from deepscout_persistence.models import ResearchRunRow
from deepscout_research.demo.presentation import (
    localized_demo_card_fields,
    normalize_locale,
    resolve_presentation,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select

from deepscout_api.deps import get_research_store
from deepscout_api.routes.research_runs import _list_item

router = APIRouter(prefix="/api/v1", tags=["demos"])


def _demo_card(row: ResearchRunRow, metrics: dict[str, int], *, locale: str | None = None) -> dict:
    item = _list_item(row, metrics).model_dump(mode="json")
    snap = row.config_snapshot or {}
    meta = snap.get("public_demo") or {}
    loc = normalize_locale(locale)
    presentation = resolve_presentation(snap, row.public_slug, loc)
    localized = localized_demo_card_fields(meta, presentation)
    item["public_slug"] = row.public_slug
    item["is_public_demo"] = row.is_public_demo
    item["demo_category"] = meta.get("category")
    item["demo_title"] = localized.get("demo_title") or row.goal
    item["demo_summary"] = localized.get("demo_summary")
    item["demo_why"] = localized.get("demo_why")
    item["demo_goal"] = localized.get("demo_goal") or row.goal
    item["presentation_locale"] = loc
    if presentation and presentation.get("goal"):
        item["goal"] = presentation["goal"]
    return item


@router.get("/demos")
def list_public_demos(
    store=Depends(get_research_store),
    locale: str | None = Query(default=None),
    x_ui_locale: str | None = Header(default=None, alias="X-UI-Locale"),
) -> dict:
    ui_locale = locale or x_ui_locale
    rows, _total = store.list_runs(limit=50, offset=0, public_demo_only=True)
    metrics = store.list_run_card_metrics([row.id for row in rows])
    items = [
        _demo_card(row, metrics[row.id], locale=ui_locale)
        for row in rows
        if row.status.value == "completed"
    ]
    return {"items": items, "total": len(items)}


@router.get("/demos/{slug}")
def get_public_demo_by_slug(
    slug: str,
    store=Depends(get_research_store),
    locale: str | None = Query(default=None),
    x_ui_locale: str | None = Header(default=None, alias="X-UI-Locale"),
) -> dict:
    row = store._session.scalar(
        select(ResearchRunRow).where(ResearchRunRow.public_slug == slug.strip().lower())
    )
    if row is None or not row.is_public_demo:
        raise HTTPException(status_code=404, detail="demo not found")
    metrics = store.list_run_card_metrics([row.id])[row.id]
    return _demo_card(row, metrics, locale=locale or x_ui_locale)
