"""Local research templates / saved presets. Hosted templates are owner-scoped."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.schemas import ResearchTemplateCreate, ResearchTemplateRead
from deepscout_core.settings import Settings, get_settings
from fastapi import APIRouter, Depends, HTTPException, Request

from deepscout_api.access import authorize_template, load_access, owner_for_create
from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/research-templates", tags=["research-templates"])


@router.get("", response_model=list[ResearchTemplateRead])
def list_templates(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[ResearchTemplateRead]:
    access = load_access(request, store._session, settings)
    if settings.is_hosted() and access.principal is None:
        return []
    owner = None if access.is_local else access.principal_id
    return store.list_templates(owner_principal_id=owner)


@router.post("", response_model=ResearchTemplateRead, status_code=201)
def create_template(
    body: ResearchTemplateCreate,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ResearchTemplateRead:
    access = load_access(request, store._session, settings)
    return store.create_template(body, owner_principal_id=owner_for_create(access))


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: UUID,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> None:
    access = load_access(request, store._session, settings)
    authorize_template(store, template_id, access)
    owner = None if access.is_local else access.principal_id
    if not store.delete_template(template_id, owner_principal_id=owner):
        raise HTTPException(status_code=404, detail="template not found")
