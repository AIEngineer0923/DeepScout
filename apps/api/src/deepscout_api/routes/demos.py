"""Public demo catalog — always read-only, no auth required on hosted."""

from __future__ import annotations

from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.models import ResearchRunRow
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from deepscout_api.deps import get_research_store
from deepscout_api.routes.research_runs import _list_item

router = APIRouter(prefix="/api/v1", tags=["demos"])


def _demo_card(row: ResearchRunRow, metrics: dict[str, int]) -> dict:
    item = _list_item(row, metrics).model_dump(mode="json")
    snap = row.config_snapshot or {}
    meta = snap.get("public_demo") or {}
    item["public_slug"] = row.public_slug
    item["is_public_demo"] = row.is_public_demo
    item["demo_category"] = meta.get("category")
    item["demo_title"] = meta.get("title") or row.goal
    item["demo_summary"] = meta.get("summary")
    item["demo_why"] = meta.get("why_interesting")
    return item


@router.get("/demos")
def list_public_demos(
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    del settings
    rows, _total = store.list_runs(limit=50, offset=0, public_demo_only=True)
    metrics = store.list_run_card_metrics([row.id for row in rows])
    items = [_demo_card(row, metrics[row.id]) for row in rows if row.status.value == "completed"]
    return {"items": items, "total": len(items)}


@router.get("/demos/{slug}")
def get_public_demo_by_slug(
    slug: str,
    store=Depends(get_research_store),
) -> dict:
    row = store._session.scalar(
        select(ResearchRunRow).where(ResearchRunRow.public_slug == slug.strip().lower())
    )
    if row is None or not row.is_public_demo:
        raise HTTPException(status_code=404, detail="demo not found")
    metrics = store.list_run_card_metrics([row.id])[row.id]
    return _demo_card(row, metrics)
