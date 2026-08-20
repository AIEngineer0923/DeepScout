"""Deterministic report generation from persisted domain state."""

from __future__ import annotations

import uuid

from deepscout_core.domain.schemas import ReportWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.prompts import REPORT_V1


@traceable(name="phase:report", run_type="chain", metadata=REPORT_V1.trace_metadata())
def generate_report(store: ResearchStore, run_id: uuid.UUID) -> uuid.UUID:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"ResearchRun {run_id} not found")
    questions = store.list_questions(run_id)
    sources = store.list_sources(run_id)
    evidence = store.list_evidence(run_id)
    decision = store.get_decision(run_id)
    contradictions = store.list_contradictions(run_id)

    lines = [
        "# Research Report",
        "",
        f"**Goal:** {run.goal}",
        "",
        "## Questions",
    ]
    for question in questions:
        lines.append(f"- ({question.status.value}) {question.text}")

    if decision is not None:
        lines.extend(
            [
                "",
                "## Synthesis",
                decision.recommendation,
                "",
                decision.rationale,
            ]
        )
    else:
        lines.extend(["", "## Synthesis", "- Insufficient verified evidence for a decision."])

    lines.extend(["", "## Sources"])
    for source in sources[:20]:
        lines.append(f"- [{source.title or source.canonical_url}]({source.canonical_url})")

    lines.extend(["", "## Evidence"])
    if evidence:
        for item in evidence[:20]:
            lines.append(f"- {item.quote[:240]}")
    else:
        lines.append("- No verified evidence attached yet.")

    if contradictions:
        lines.extend(["", "## Contradictions"])
        for row in contradictions[:10]:
            lines.append(f"- {row.description[:240]}")

    body = "\n".join(lines)
    if evidence:
        report = store.save_report(
            run_id,
            ReportWrite(
                title="Research Report",
                body_markdown=body,
                cited_evidence_ids=[item.id for item in evidence[:20]],
            ),
        )
        return report.id

    report = store.save_report_draft(
        run_id,
        title="Research Report (candidate sources only)",
        body_markdown=body,
    )
    return report.id
