"""Run-scoped compiled knowledge persistence — derived from claims, never evidence."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from deepscout_core.domain.enums import (
    KnowledgeProvenanceKind,
    KnowledgeRelationType,
    WikiChangeOp,
    WikiLinkType,
    WikiPageStatus,
    WikiPageType,
    WikiStatementStatus,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from deepscout_persistence.models import (
    ClaimRow,
    EvidenceRow,
    KnowledgeRelationRow,
    WikiLinkRow,
    WikiPageRow,
    WikiRevisionRow,
    WikiStatementRow,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str, *, fallback: str) -> str:
    cleaned = _SLUG_RE.sub("-", value.lower()).strip("-")
    return (cleaned or fallback)[:180]


def get_page_by_slug(session: Session, run_id: uuid.UUID, slug: str) -> WikiPageRow | None:
    return session.scalar(
        select(WikiPageRow).where(WikiPageRow.research_run_id == run_id, WikiPageRow.slug == slug)
    )


def list_pages_for_run(session: Session, run_id: uuid.UUID) -> list[WikiPageRow]:
    return list(
        session.scalars(select(WikiPageRow).where(WikiPageRow.research_run_id == run_id)).all()
    )


def list_statements_for_run(session: Session, run_id: uuid.UUID) -> list[WikiStatementRow]:
    return list(
        session.scalars(
            select(WikiStatementRow).where(WikiStatementRow.research_run_id == run_id)
        ).all()
    )


def create_page(
    session: Session,
    *,
    run_id: uuid.UUID,
    slug: str,
    title: str,
    page_type: WikiPageType,
    body_markdown: str = "",
) -> WikiPageRow:
    existing = get_page_by_slug(session, run_id, slug)
    if existing is not None:
        if existing.research_run_id != run_id:
            raise PermissionError("wiki page run_id mismatch")
        return existing
    page = WikiPageRow(
        research_run_id=run_id,
        slug=slug,
        title=title,
        page_type=page_type,
        status=WikiPageStatus.ACTIVE,
        version=1,
        body_markdown=body_markdown,
    )
    session.add(page)
    session.flush()
    session.add(
        WikiRevisionRow(
            page_id=page.id,
            revision=1,
            body_markdown=body_markdown,
            change_op=WikiChangeOp.CREATE,
        )
    )
    session.flush()
    return page


def revise_page(
    session: Session,
    page: WikiPageRow,
    *,
    body_markdown: str,
    change_op: WikiChangeOp,
) -> WikiPageRow:
    if body_markdown == page.body_markdown:
        return page
    page.body_markdown = body_markdown
    page.version += 1
    page.updated_at = datetime.now(UTC)
    session.add(
        WikiRevisionRow(
            page_id=page.id,
            revision=page.version,
            body_markdown=body_markdown,
            change_op=change_op,
        )
    )
    session.flush()
    return page


def add_statement(
    session: Session,
    *,
    run_id: uuid.UUID,
    page_id: uuid.UUID,
    statement_text: str,
    claim_id: uuid.UUID | None,
    evidence_id: uuid.UUID | None,
) -> WikiStatementRow:
    page = session.get(WikiPageRow, page_id)
    if page is None or page.research_run_id != run_id:
        raise PermissionError("wiki statement page must belong to the same run")
    if claim_id is not None:
        claim = session.get(ClaimRow, claim_id)
        if claim is None or claim.research_run_id != run_id:
            raise PermissionError("claim provenance must belong to the same run")
        existing = session.scalar(
            select(WikiStatementRow).where(
                WikiStatementRow.research_run_id == run_id,
                WikiStatementRow.claim_id == claim_id,
            )
        )
        if existing is not None:
            return existing
    if evidence_id is not None:
        evidence = session.get(EvidenceRow, evidence_id)
        if evidence is None:
            raise LookupError(f"Evidence {evidence_id} not found")
        claim = session.get(ClaimRow, evidence.claim_id)
        if claim is None or claim.research_run_id != run_id:
            raise PermissionError("evidence provenance must belong to the same run")
    row = WikiStatementRow(
        page_id=page_id,
        research_run_id=run_id,
        statement_text=statement_text,
        status=WikiStatementStatus.ACTIVE,
        claim_id=claim_id,
        evidence_id=evidence_id,
        version=1,
    )
    session.add(row)
    session.flush()
    return row


def add_link(
    session: Session,
    *,
    run_id: uuid.UUID,
    from_page_id: uuid.UUID,
    to_page_id: uuid.UUID,
    link_type: WikiLinkType,
) -> WikiLinkRow:
    for page_id in (from_page_id, to_page_id):
        page = session.get(WikiPageRow, page_id)
        if page is None or page.research_run_id != run_id:
            raise PermissionError("wiki link pages must belong to the same run")
    existing = session.scalar(
        select(WikiLinkRow).where(
            WikiLinkRow.from_page_id == from_page_id,
            WikiLinkRow.to_page_id == to_page_id,
            WikiLinkRow.link_type == link_type,
        )
    )
    if existing is not None:
        return existing
    row = WikiLinkRow(
        research_run_id=run_id,
        from_page_id=from_page_id,
        to_page_id=to_page_id,
        link_type=link_type,
    )
    session.add(row)
    session.flush()
    return row


def add_relation(
    session: Session,
    *,
    run_id: uuid.UUID,
    relation_type: KnowledgeRelationType,
    provenance_kind: KnowledgeProvenanceKind,
    from_statement_id: uuid.UUID | None = None,
    to_statement_id: uuid.UUID | None = None,
    claim_a_id: uuid.UUID | None = None,
    claim_b_id: uuid.UUID | None = None,
) -> KnowledgeRelationRow:
    row = KnowledgeRelationRow(
        research_run_id=run_id,
        from_statement_id=from_statement_id,
        to_statement_id=to_statement_id,
        relation_type=relation_type,
        provenance_kind=provenance_kind,
        claim_a_id=claim_a_id,
        claim_b_id=claim_b_id,
    )
    session.add(row)
    session.flush()
    return row


def query_compiled_statements(
    session: Session,
    *,
    run_id: uuid.UUID,
    query: str,
    limit: int = 8,
) -> list[WikiStatementRow]:
    """Lexical search over compiled statements only — never mixed with RAW chunks."""
    tokens = [token for token in re.findall(r"[a-z0-9-]{3,}", query.lower())][:8]
    rows = list_statements_for_run(session, run_id)
    if not tokens:
        return rows[:limit]
    scored: list[tuple[int, WikiStatementRow]] = []
    for row in rows:
        if row.status != WikiStatementStatus.ACTIVE:
            continue
        blob = row.statement_text.lower()
        score = sum(1 for token in tokens if token in blob)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def _maybe_link_claim_relation(
    session: Session,
    *,
    run_id: uuid.UUID,
    claim: ClaimRow,
    evidence: EvidenceRow,
) -> None:
    """Link new statement to prior statements from the same source (bounded graph)."""
    if claim.source_id is None:
        return
    new_stmt = session.scalar(
        select(WikiStatementRow).where(
            WikiStatementRow.research_run_id == run_id,
            WikiStatementRow.claim_id == claim.id,
        )
    )
    if new_stmt is None:
        return
    peers = session.scalars(
        select(WikiStatementRow)
        .join(ClaimRow, ClaimRow.id == WikiStatementRow.claim_id)
        .where(
            WikiStatementRow.research_run_id == run_id,
            ClaimRow.source_id == claim.source_id,
            WikiStatementRow.id != new_stmt.id,
        )
        .limit(5)
    ).all()
    for peer in peers:
        add_relation(
            session,
            run_id=run_id,
            relation_type=KnowledgeRelationType.RELATED_TO,
            provenance_kind=KnowledgeProvenanceKind.DETERMINISTIC,
            from_statement_id=peer.id,
            to_statement_id=new_stmt.id,
            claim_a_id=peer.claim_id,
            claim_b_id=claim.id,
        )


def rebuild_wiki_from_claims(session: Session, run_id: uuid.UUID) -> dict[str, int]:
    """Deterministic Knowledge Compiler — CREATE/CONFIRM from claims with evidence."""
    findings = create_page(
        session,
        run_id=run_id,
        slug="run-findings",
        title="Run findings",
        page_type=WikiPageType.FINDING,
        body_markdown="# Run findings\n\nCompiled from verified claim/evidence pairs.\n",
    )
    claims = list(session.scalars(select(ClaimRow).where(ClaimRow.research_run_id == run_id)).all())
    created = confirmed = skipped = pages = 0
    entity_pages: dict[uuid.UUID, WikiPageRow] = {}
    for claim in claims:
        evidence_items = list(
            session.scalars(select(EvidenceRow).where(EvidenceRow.claim_id == claim.id)).all()
        )
        if not evidence_items:
            skipped += 1
            continue
        evidence = evidence_items[0]
        page = findings
        if claim.source_id is not None:
            if claim.source_id not in entity_pages:
                slug = _slugify(f"source-{claim.source_id}", fallback="source")
                entity_pages[claim.source_id] = create_page(
                    session,
                    run_id=run_id,
                    slug=slug,
                    title=f"Source {claim.source_id}",
                    page_type=WikiPageType.ENTITY,
                    body_markdown=f"# Source {claim.source_id}\n",
                )
                pages += 1
                add_link(
                    session,
                    run_id=run_id,
                    from_page_id=findings.id,
                    to_page_id=entity_pages[claim.source_id].id,
                    link_type=WikiLinkType.DERIVED_FROM,
                )
            page = entity_pages[claim.source_id]
        existing = session.scalar(
            select(WikiStatementRow).where(
                WikiStatementRow.research_run_id == run_id,
                WikiStatementRow.claim_id == claim.id,
            )
        )
        if existing is not None:
            confirmed += 1
            continue
        add_statement(
            session,
            run_id=run_id,
            page_id=page.id,
            statement_text=claim.statement,
            claim_id=claim.id,
            evidence_id=evidence.id,
        )
        created += 1
        _maybe_link_claim_relation(session, run_id=run_id, claim=claim, evidence=evidence)
        bullet = f"- {claim.statement[:240]}"
        if bullet not in findings.body_markdown:
            revise_page(
                session,
                findings,
                body_markdown=findings.body_markdown.rstrip() + "\n" + bullet + "\n",
                change_op=WikiChangeOp.CONFIRM if confirmed else WikiChangeOp.CREATE,
            )
    session.flush()
    return {
        "pages": len(list_pages_for_run(session, run_id)),
        "statements_created": created,
        "statements_confirmed": confirmed,
        "claims_skipped_no_evidence": skipped,
        "entity_pages_touched": pages,
    }


def bounded_relation_hops(
    session: Session,
    *,
    run_id: uuid.UUID,
    max_hops: int = 3,
) -> list[tuple[int, int]]:
    """Return (hop, edge_count) for a bounded recursive walk. max_hops is hard-capped at 3."""
    from sqlalchemy import text

    hops = min(3, max(1, int(max_hops)))
    rows = session.execute(
        text(
            """
            WITH RECURSIVE walk AS (
                SELECT from_statement_id AS src,
                       to_statement_id AS dst,
                       1 AS hop
                FROM knowledge_relations
                WHERE research_run_id = :run_id
                  AND from_statement_id IS NOT NULL
                  AND to_statement_id IS NOT NULL
                UNION ALL
                SELECT walk.src,
                       kr.to_statement_id,
                       walk.hop + 1
                FROM walk
                JOIN knowledge_relations kr
                  ON kr.from_statement_id = walk.dst
                 AND kr.research_run_id = :run_id
                WHERE walk.hop < :max_hops
                  AND kr.to_statement_id IS NOT NULL
            )
            SELECT hop, count(*)::int AS n
            FROM walk
            GROUP BY hop
            ORDER BY hop
            """
        ),
        {"run_id": run_id, "max_hops": hops},
    ).all()
    return [(int(hop), int(n)) for hop, n in rows]


def lint_wiki(session: Session, run_id: uuid.UUID, *, max_hops: int = 32) -> dict:
    pages = {page.id: page for page in list_pages_for_run(session, run_id)}
    statements = list_statements_for_run(session, run_id)
    links = list(
        session.scalars(select(WikiLinkRow).where(WikiLinkRow.research_run_id == run_id)).all()
    )
    broken_links = []
    for link in links:
        if link.from_page_id not in pages or link.to_page_id not in pages:
            broken_links.append(str(link.id))
    inbound = {page_id: 0 for page_id in pages}
    for link in links:
        if link.to_page_id in inbound:
            inbound[link.to_page_id] += 1
    orphan_pages = [
        str(page_id)
        for page_id, count in inbound.items()
        if count == 0 and pages[page_id].slug != "run-findings"
    ]
    missing_provenance = [
        str(row.id) for row in statements if row.claim_id is None or row.evidence_id is None
    ]
    # Bound cycle detection: BFS from each page up to max_hops
    adjacency: dict[uuid.UUID, list[uuid.UUID]] = {page_id: [] for page_id in pages}
    for link in links:
        adjacency.setdefault(link.from_page_id, []).append(link.to_page_id)
    cyclic_nodes: set[str] = set()
    for start in pages:
        seen: set[uuid.UUID] = set()
        stack = [(start, 0, {start})]
        while stack and len(seen) < max_hops:
            node, depth, path = stack.pop()
            if depth >= max_hops:
                continue
            seen.add(node)
            for nxt in adjacency.get(node, []):
                if nxt in path:
                    cyclic_nodes.add(str(nxt))
                    continue
                stack.append((nxt, depth + 1, path | {nxt}))
    return {
        "broken_links": broken_links,
        "orphan_pages": orphan_pages,
        "statements_without_provenance": missing_provenance,
        "cyclic_nodes_bounded": sorted(cyclic_nodes)[:50],
        "page_count": len(pages),
        "statement_count": len(statements),
    }
