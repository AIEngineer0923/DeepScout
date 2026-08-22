"""Local graph retrieval over knowledge_relations — not full GraphRAG communities."""

from __future__ import annotations

import re
import uuid

from deepscout_persistence.knowledge import list_statements_for_run
from deepscout_persistence.models import KnowledgeRelationRow, WikiStatementRow
from sqlalchemy import select
from sqlalchemy.orm import Session

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}")


def graph_search_statements(
    session: Session,
    *,
    run_id: uuid.UUID,
    query: str,
    limit: int = 8,
    max_hops: int = 1,
) -> list[tuple[WikiStatementRow, str]]:
    """Return (statement, reason) pairs from entity match + bounded relation expansion."""
    tokens = _TOKEN_RE.findall(query.lower())[:12]
    if not tokens:
        return []
    statements = list_statements_for_run(session, run_id)
    if not statements:
        return []

    by_id = {row.id: row for row in statements}
    seed_ids: list[uuid.UUID] = []
    for row in statements:
        blob = row.statement_text.lower()
        if any(token in blob for token in tokens):
            seed_ids.append(row.id)

    if not seed_ids:
        return []

    expanded: dict[uuid.UUID, str] = {sid: "entity_match" for sid in seed_ids}
    if max_hops >= 1:
        relations = session.scalars(
            select(KnowledgeRelationRow).where(KnowledgeRelationRow.research_run_id == run_id)
        ).all()
        frontier = set(seed_ids)
        for _hop in range(max_hops):
            next_frontier: set[uuid.UUID] = set()
            for rel in relations:
                if rel.from_statement_id in frontier and rel.to_statement_id:
                    tid = rel.to_statement_id
                    if tid not in expanded and tid in by_id:
                        expanded[tid] = f"graph_hop_{_hop + 1}"
                        next_frontier.add(tid)
                if rel.to_statement_id in frontier and rel.from_statement_id:
                    fid = rel.from_statement_id
                    if fid not in expanded and fid in by_id:
                        expanded[fid] = f"graph_hop_{_hop + 1}"
                        next_frontier.add(fid)
            frontier = next_frontier
            if not frontier:
                break

    ranked = sorted(
        expanded.items(),
        key=lambda item: (0 if item[1] == "entity_match" else 1, str(item[0])),
    )
    out: list[tuple[WikiStatementRow, str]] = []
    for stmt_id, reason in ranked[:limit]:
        row = by_id.get(stmt_id)
        if row is not None:
            out.append((row, reason))
    return out
