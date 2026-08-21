"""Compiled knowledge browser — run-scoped Wiki is derived, not evidence."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.knowledge import (
    bounded_relation_hops,
    list_pages_for_run,
    list_statements_for_run,
    query_compiled_statements,
)
from deepscout_persistence.models import (
    ClaimRow,
    KnowledgeRelationRow,
    SourceRow,
    SourceSnapshotRow,
    WikiLinkRow,
    WikiPageRow,
    WikiRevisionRow,
    WikiStatementRow,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from deepscout_api.access import authorize_run, load_access
from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _page_payload(page: WikiPageRow) -> dict:
    return {
        "id": str(page.id),
        "run_id": str(page.research_run_id),
        "slug": page.slug,
        "title": page.title,
        "page_type": page.page_type.value,
        "status": page.status.value,
        "version": page.version,
        "body_markdown": page.body_markdown,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
        "authority": "compiled_knowledge",
        "not_evidence": True,
    }


@router.get("/runs")
def knowledge_runs(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    access = load_access(request, store._session, settings)
    public_only = settings.is_hosted() and access.principal is None
    owner = access.principal_id if not access.is_local and not public_only else None
    rows, _ = store.list_runs(
        status="completed",
        limit=40,
        offset=0,
        owner_principal_id=owner,
        public_demo_only=public_only,
    )
    out = []
    for row in rows:
        pages = list_pages_for_run(store._session, row.id)
        if not pages:
            continue
        out.append({"run_id": str(row.id), "goal": row.goal, "page_count": len(pages)})
    return out


@router.get("/pages")
def knowledge_pages(
    run_id: UUID,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    access = load_access(request, store._session, settings)
    authorize_run(store, run_id, access, write=False)
    return [_page_payload(page) for page in list_pages_for_run(store._session, run_id)]


@router.get("/pages/{page_id}")
def knowledge_page(
    page_id: UUID,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    page = store._session.get(WikiPageRow, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    access = load_access(request, store._session, settings)
    authorize_run(store, page.research_run_id, access, write=False)
    statements = [
        row
        for row in list_statements_for_run(store._session, page.research_run_id)
        if row.page_id == page.id
    ]
    revisions = list(
        store._session.scalars(
            select(WikiRevisionRow)
            .where(WikiRevisionRow.page_id == page.id)
            .order_by(WikiRevisionRow.revision.desc())
        ).all()
    )
    links = list(
        store._session.scalars(select(WikiLinkRow).where(WikiLinkRow.from_page_id == page.id)).all()
    )
    return {
        **_page_payload(page),
        "statements": [
            {
                "id": str(row.id),
                "text": row.statement_text,
                "status": row.status.value,
                "claim_id": str(row.claim_id) if row.claim_id else None,
            }
            for row in statements
        ],
        "revisions": [
            {
                "id": str(row.id),
                "revision": row.revision,
                "change_op": row.change_op.value,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in revisions[:20]
        ],
        "links": [
            {"to_page_id": str(row.to_page_id), "link_type": row.link_type.value}
            for row in links[:50]
        ],
    }


@router.get("/statements/{statement_id}")
def knowledge_statement(
    statement_id: UUID,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    statement = store._session.get(WikiStatementRow, statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="statement not found")
    access = load_access(request, store._session, settings)
    authorize_run(store, statement.research_run_id, access, write=False)
    claim = store._session.get(ClaimRow, statement.claim_id) if statement.claim_id else None
    evidence_rows = []
    if claim is not None:
        evidence_rows = store.list_evidence_for_claim(claim.id)
    provenance = []
    for item in evidence_rows:
        snap = store._session.get(SourceSnapshotRow, item.snapshot_id)
        source = store._session.get(SourceRow, snap.source_id) if snap is not None else None
        provenance.append(
            {
                "evidence_id": str(item.id),
                "quote": item.quote,
                "snapshot_id": str(item.snapshot_id),
                "passage": (snap.content_text or "")[:800] if snap is not None else "",
                "source_id": str(source.id) if source else None,
                "source_url": source.canonical_url if source else None,
            }
        )
    relations = list(
        store._session.scalars(
            select(KnowledgeRelationRow).where(
                (KnowledgeRelationRow.from_statement_id == statement.id)
                | (KnowledgeRelationRow.to_statement_id == statement.id)
            )
        ).all()
    )[:40]
    return {
        "id": str(statement.id),
        "run_id": str(statement.research_run_id),
        "page_id": str(statement.page_id),
        "text": statement.statement_text,
        "status": statement.status.value,
        "claim": {"id": str(claim.id), "statement": claim.statement} if claim else None,
        "provenance": provenance,
        "relations": [
            {
                "id": str(row.id),
                "type": row.relation_type.value,
                "from_statement_id": str(row.from_statement_id) if row.from_statement_id else None,
                "to_statement_id": str(row.to_statement_id) if row.to_statement_id else None,
            }
            for row in relations
        ],
        "not_evidence": True,
    }


@router.get("/search")
def knowledge_search(
    run_id: UUID,
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    authorize_run(store, run_id, access, write=False)
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    hits = query_compiled_statements(store._session, run_id=run_id, query=q, limit=20)[:20]
    return {
        "layer": "compiled_knowledge",
        "not_evidence": True,
        "items": [
            {
                "id": str(row.id),
                "text": row.statement_text,
                "page_id": str(row.page_id),
                "status": row.status.value,
            }
            for row in hits
        ],
    }


@router.get("/graph")
def knowledge_graph(
    run_id: UUID,
    request: Request,
    hops: int = Query(default=2, ge=1, le=3),
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    authorize_run(store, run_id, access, write=False)
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    statements = list_statements_for_run(store._session, run_id)[:80]
    relations = list(
        store._session.scalars(
            select(KnowledgeRelationRow)
            .where(KnowledgeRelationRow.research_run_id == run_id)
            .limit(120)
        ).all()
    )
    hop_counts = bounded_relation_hops(store._session, run_id=run_id, max_hops=hops)
    return {
        "bounded": True,
        "max_hops": hops,
        "hop_counts": [{"hop": hop, "edges": n} for hop, n in hop_counts],
        "nodes": [
            {"id": str(row.id), "label": row.statement_text[:80], "status": row.status.value}
            for row in statements
        ],
        "edges": [
            {
                "from": str(row.from_statement_id) if row.from_statement_id else None,
                "to": str(row.to_statement_id) if row.to_statement_id else None,
                "type": row.relation_type.value,
            }
            for row in relations
            if row.from_statement_id and row.to_statement_id
        ],
    }
