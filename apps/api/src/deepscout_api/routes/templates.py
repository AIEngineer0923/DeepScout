"""Local research templates / saved presets. MODE A — no accounts."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.schemas import ResearchTemplateCreate, ResearchTemplateRead
from fastapi import APIRouter, Depends, HTTPException

from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/research-templates", tags=["research-templates"])


@router.get("", response_model=list[ResearchTemplateRead])
def list_templates(store=Depends(get_research_store)) -> list[ResearchTemplateRead]:
    return store.list_templates()


@router.post("", response_model=ResearchTemplateRead, status_code=201)
def create_template(
    body: ResearchTemplateCreate,
    store=Depends(get_research_store),
) -> ResearchTemplateRead:
    return store.create_template(body)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: UUID, store=Depends(get_research_store)) -> None:
    if not store.delete_template(template_id):
        raise HTTPException(status_code=404, detail="template not found")
