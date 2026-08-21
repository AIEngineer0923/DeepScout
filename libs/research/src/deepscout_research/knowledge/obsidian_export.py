"""Optional Obsidian-compatible Markdown export — not a runtime dependency."""

from __future__ import annotations

import re
import uuid

from deepscout_persistence.knowledge import list_pages_for_run, list_statements_for_run
from deepscout_persistence.store import ResearchStore

_JS_URL = re.compile(r"(?i)javascript\s*:")
_HTML_TAG = re.compile(r"<[^>]+>")


def sanitize_export_text(value: str) -> str:
    cleaned = _JS_URL.sub("", value)
    cleaned = _HTML_TAG.sub("", cleaned)
    return cleaned.replace("\x00", "")


def export_run_wiki_markdown(store: ResearchStore, run_id: uuid.UUID) -> dict[str, str]:
    session = store._session
    pages = list_pages_for_run(session, run_id)
    statements = list_statements_for_run(session, run_id)
    by_page: dict[uuid.UUID, list] = {}
    for statement in statements:
        by_page.setdefault(statement.page_id, []).append(statement)

    files: dict[str, str] = {}
    for page in pages:
        folder = {
            "topic": "topics",
            "entity": "entities",
            "concept": "concepts",
            "finding": "findings",
            "contradiction": "contradictions",
            "question": "questions",
        }.get(page.page_type.value, "topics")
        claim_ids = [
            str(item.claim_id) for item in by_page.get(page.id, []) if item.claim_id is not None
        ]
        frontmatter = "\n".join(
            [
                "---",
                f"id: {page.id}",
                f"title: {sanitize_export_text(page.title)}",
                f"type: {page.page_type.value}",
                f"version: {page.version}",
                f"claim_ids: [{', '.join(claim_ids)}]",
                "---",
                "",
            ]
        )
        body = sanitize_export_text(page.body_markdown)
        stmt_lines = []
        for item in by_page.get(page.id, []):
            stmt_lines.append(f"- {sanitize_export_text(item.statement_text)}")
            if item.claim_id and item.evidence_id:
                stmt_lines.append(f"  - claim: `{item.claim_id}` evidence: `{item.evidence_id}`")
        content = frontmatter + body.rstrip() + "\n"
        if stmt_lines:
            content += "\n## Statements\n\n" + "\n".join(stmt_lines) + "\n"
        files[f"vault/{folder}/{page.slug}.md"] = content
    return files
