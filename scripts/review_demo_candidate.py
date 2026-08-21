"""Operator quality review for a candidate public demo run."""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore


def review_run(store: ResearchStore, run_id: UUID) -> dict:
    row = store.get_run_row(run_id)
    if row is None:
        raise SystemExit("run not found")
    tasks = store.list_tasks(run_id)
    sources = store.list_sources(run_id)
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    contradictions = store.list_contradictions(run_id)
    report = store.get_report(run_id)
    events = store.list_run_events(run_id)
    usage = store.get_usage_summary(run_id)

    dependency_edges = sum(1 for task in tasks if task.depends_on)
    unique_domains = {source.domain for source in sources if source.domain}
    unresolved_quotes = sum(1 for item in evidence if not (item.quote or "").strip())
    report_citations = (report.body_markdown or "").count("](") if report else 0

    checks = {
        "RESEARCH QUALITY": row.status.value == "completed",
        "PLANNER": len(tasks) >= 1,
        "DAG": len(tasks) >= 2 and dependency_edges >= 1,
        "SOURCES": len(sources) >= 3 and len(unique_domains) >= 2,
        "EVIDENCE": len(evidence) >= len(claims) // 2 if claims else False,
        "PROVENANCE": len(evidence) >= 1 and unresolved_quotes == 0,
        "REPORT": report is not None and len((report.body_markdown or "").strip()) > 200,
        "WIKI": True,
        "SECURITY": "[redacted]" not in (row.goal or ""),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    return {
        "run_id": str(run_id),
        "slug": row.public_slug,
        "status": row.status.value,
        "tasks": len(tasks),
        "dependency_edges": dependency_edges,
        "sources": len(sources),
        "unique_domains": len(unique_domains),
        "claims": len(claims),
        "evidence": len(evidence),
        "contradictions": len(contradictions),
        "report_citations": report_citations,
        "events": len(events),
        "tokens": usage.total_tokens,
        "cost_usd": usage.cost_usd,
        "checks": checks,
        "PUBLICATION DECISION": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    args = parser.parse_args()
    settings = Settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    try:
        payload = review_run(store, UUID(args.run_id))
    finally:
        session.close()
    print(json.dumps(payload, indent=2))
    return 0 if payload["PUBLICATION DECISION"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
