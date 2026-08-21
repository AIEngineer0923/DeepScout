"""Deterministic public demo quality gate."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_persistence.store import ResearchStore

from deepscout_research.demo.catalog import DEMO_BY_SLUG


def _independent_domains(sources) -> set[str]:
    roots: set[str] = set()
    for source in sources:
        domain = (source.domain or "").lower().strip()
        if not domain:
            continue
        parts = domain.split(".")
        root = ".".join(parts[-2:]) if len(parts) >= 2 else domain
        roots.add(root)
    return roots


def review_demo_candidate(
    store: ResearchStore, run_id: UUID, *, slug: str | None = None
) -> dict[str, Any]:
    row = store.get_run_row(run_id)
    if row is None:
        raise LookupError("run not found")
    meta = DEMO_BY_SLUG.get(slug or row.public_slug or "")
    category = (meta or {}).get("category", "general")

    tasks = store.list_tasks(run_id)
    sources = store.list_sources(run_id)
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    contradictions = store.list_contradictions(run_id)
    report = store.get_report(run_id)
    events = store.list_run_events(run_id)
    usage = store.get_usage_summary(run_id)

    dependency_edges = sum(1 for task in tasks if task.depends_on)
    unique_domains = _independent_domains(sources)
    unresolved_quotes = sum(1 for item in evidence if not (item.quote or "").strip())
    report_body = (report.body_markdown or "").strip() if report else ""
    report_citations = report_body.count("](")

    checks: dict[str, bool] = {
        "TERMINAL_COMPLETED": row.status.value == "completed",
        "PLANNER": len(tasks) >= 1,
        "REPORT_PRESENT": len(report_body) > 300,
        "SOURCES_PRESENT": len(sources) >= 1,
        "EVIDENCE_PRESENT": len(evidence) >= 1,
        "PROVENANCE_QUOTES": unresolved_quotes == 0,
        "SECURITY_CLEAN": "[redacted]" not in report_body and "sk-" not in report_body,
    }

    reasons: list[str] = []
    warnings: list[str] = []

    min_sources = 3 if category in {"technical", "scientific", "regulatory", "contradiction"} else 2
    if len(sources) < min_sources:
        checks["SOURCE_BREADTH"] = False
        reasons.append(f"SOURCE_QUALITY_FAILURE: only {len(sources)} sources (need {min_sources})")
    else:
        checks["SOURCE_BREADTH"] = True

    if len(unique_domains) < min(2, len(sources)):
        checks["SOURCE_DIVERSITY"] = len(sources) <= 1
        if len(sources) > 1:
            reasons.append("SOURCE_QUALITY_FAILURE: insufficient independent domains")
    else:
        checks["SOURCE_DIVERSITY"] = True

    if category == "multi-hop":
        dag_ok = len(tasks) >= 2 and dependency_edges >= 1
        checks["DAG_DEPENDENCY"] = dag_ok
        if not dag_ok:
            reasons.append("RUNTIME_DEFECT: multi-hop demo lacks dependency edge")
    else:
        checks["DAG_DEPENDENCY"] = True

    if claims and len(evidence) < max(1, len(claims) // 2):
        checks["EVIDENCE_COVERAGE"] = False
        reasons.append("EVIDENCE_QUALITY_FAILURE: sparse evidence for claims")
    else:
        checks["EVIDENCE_COVERAGE"] = True

    if report_citations < 1 and len(claims) > 0:
        warnings.append("REPORT_WARN: no markdown citations detected")

    hard_fail = [name for name, ok in checks.items() if not ok]
    if hard_fail:
        verdict = "FAIL"
    elif warnings:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {
        "run_id": str(run_id),
        "slug": slug or row.public_slug,
        "category": category,
        "status": row.status.value,
        "tasks": len(tasks),
        "dependency_edges": dependency_edges,
        "sources": len(sources),
        "independent_domains": len(unique_domains),
        "claims": len(claims),
        "evidence": len(evidence),
        "contradictions": len(contradictions),
        "report_citations": report_citations,
        "events": len(events),
        "tokens": usage.total_tokens,
        "cost_usd": usage.cost_usd,
        "checks": checks,
        "reason_codes": reasons,
        "warnings": warnings,
        "PUBLICATION_DECISION": verdict,
    }
