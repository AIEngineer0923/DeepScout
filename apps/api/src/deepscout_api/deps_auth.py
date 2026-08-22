"""FastAPI dependencies that enforce run authorization before request-body parsing."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.store import ResearchStore
from fastapi import Depends, Request

from deepscout_api.access import authorize_run, load_access
from deepscout_api.deps import get_research_store


def require_run_write(
    run_id: UUID,
    request: Request,
    store: Annotated[ResearchStore, Depends(get_research_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResearchRunRow:
    access = load_access(request, store._session, settings)
    return authorize_run(store, run_id, access, write=True)


def require_run_read(
    run_id: UUID,
    request: Request,
    store: Annotated[ResearchStore, Depends(get_research_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResearchRunRow:
    access = load_access(request, store._session, settings)
    return authorize_run(store, run_id, access, write=False)


WriteRunDep = Annotated[ResearchRunRow, Depends(require_run_write)]
ReadRunDep = Annotated[ResearchRunRow, Depends(require_run_read)]
