"""Goal-conditioned report generation from contracts, coverage, and verified evidence."""

from __future__ import annotations

import uuid
from collections import OrderedDict

from deepscout_core.domain.contracts import (
    CoverageMap,
    RequirementCoverageStatus,
    ResearchContract,
)
from deepscout_core.domain.enums import ClaimVerificationStatus
from deepscout_core.domain.schemas import ReportWrite
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import (
    build_research_contract,
    contract_from_snapshot,
    derive_report_contract,
    report_contract_from_snapshot,
)
from deepscout_research.prompts import REPORT_V1
from deepscout_research.phases.report_synthesis import synthesize_goal_conditioned_report


def _section_heading(spec_heading: str, language: str) -> str:
    if language.startswith("it"):
        mapping = {
            "Executive Summary": "Sintesi esecutiva",
            "Analysis": "Analisi",
            "Timeline and Applicability": "Cronologia e applicabilità",
            "Comparison": "Confronto",
            "Quantitative Results": "Risultati quantitativi",
            "Limitations and Uncertainty": "Limitazioni e incertezza",
            "Sources Cited": "Fonti citate",
            "Questions Answered": "Domande affrontate",
        }
        return mapping.get(spec_heading, spec_heading)
    return spec_heading


def _status_label(status: RequirementCoverageStatus, language: str) -> str:
    if language.startswith("it"):
        labels = {
            RequirementCoverageStatus.SUPPORTED: "supportato",
            RequirementCoverageStatus.PARTIAL: "parziale",
            RequirementCoverageStatus.CONFLICTING: "conflittuale",
            RequirementCoverageStatus.UNSUPPORTED: "non supportato",
            RequirementCoverageStatus.SEARCHED_NO_EVIDENCE: "evidenza insufficiente",
            RequirementCoverageStatus.EVIDENCE_FOUND: "evidenza trovata",
            RequirementCoverageStatus.SEARCHED: "ricercato",
            RequirementCoverageStatus.NOT_RESEARCHED: "non ricercato",
        }
        return labels.get(status, status.value.replace("_", " "))
    return status.value.replace("_", " ")


def _collect_cited_sources(
    store: ResearchStore,
    run_id: uuid.UUID,
) -> tuple[list, list[uuid.UUID]]:
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    sources_by_id = {source.id: source for source in store.list_sources(run_id)}
    verified = {
        ClaimVerificationStatus.VERIFIED,
        ClaimVerificationStatus.PARTIALLY_VERIFIED,
    }
    cited_evidence_ids: list[uuid.UUID] = []
    source_ids: OrderedDict[uuid.UUID, object] = OrderedDict()
    evidence_by_claim = {item.claim_id: item for item in evidence}
    for claim in claims:
        if claim.verification_status not in verified:
            continue
        if claim.source_id is None:
            continue
        ev = evidence_by_claim.get(claim.id)
        if ev is None:
            continue
        source = sources_by_id.get(claim.source_id)
        if source is None:
            continue
        source_ids[source.id] = source
        cited_evidence_ids.append(ev.id)
    return list(source_ids.values()), cited_evidence_ids


def _render_coverage_section(
    contract: ResearchContract,
    coverage: CoverageMap,
    language: str,
) -> list[str]:
    lines = ["", f"## {_section_heading('Limitations and Uncertainty', language)}"]
    for entry in coverage.entries:
        req = next(
            (item for item in contract.requirements if item.requirement_id == entry.requirement_id),
            None,
        )
        if req is None:
            continue
        if entry.status in {RequirementCoverageStatus.SUPPORTED}:
            continue
        label = _status_label(entry.status, language)
        note = f" — {entry.note}" if entry.note else ""
        lines.append(f"- **{req.text[:180]}**: {label}{note}")
    if len(lines) == 2:
        if language.startswith("it"):
            lines.append("- Nessuna limitazione materiale oltre a quelle discusse nell'analisi.")
        else:
            lines.append("- No material limitations beyond those discussed in the analysis.")
    return lines


def _archive_report_revision(store: ResearchStore, run_id: uuid.UUID, report) -> None:
    if report is None:
        return
    row = store.get_run_row(run_id)
    snapshot = dict(row.config_snapshot or {})
    revisions = list(snapshot.get("report_revisions") or [])
    revisions.append(
        {
            "report_id": str(report.id),
            "title": report.title,
            "created_at": report.created_at.isoformat() if report.created_at else "",
            "finalizer": "report_v2",
        }
    )
    snapshot["report_revisions"] = revisions[-10:]
    store.merge_config_snapshot(run_id, snapshot)


def _evidence_ids_for_claims(store: ResearchStore, run_id: uuid.UUID, claim_ids: list[uuid.UUID]):
    if not claim_ids:
        return _collect_cited_sources(store, run_id)
    claims = {claim.id: claim for claim in store.list_claims(run_id)}
    evidence = store.list_evidence(run_id)
    evidence_by_claim = {item.claim_id: item for item in evidence}
    sources_by_id = {source.id: source for source in store.list_sources(run_id)}
    cited_evidence_ids: list[uuid.UUID] = []
    source_ids: OrderedDict[uuid.UUID, object] = OrderedDict()
    for claim_id in claim_ids:
        claim = claims.get(claim_id)
        if claim is None or claim.source_id is None:
            continue
        ev = evidence_by_claim.get(claim.id)
        if ev is None:
            continue
        source = sources_by_id.get(claim.source_id)
        if source is None:
            continue
        source_ids[source.id] = source
        cited_evidence_ids.append(ev.id)
    if cited_evidence_ids:
        return list(source_ids.values()), cited_evidence_ids
    return _collect_cited_sources(store, run_id)


def _append_sources_cited(body: str, cited_sources, language: str) -> str:
    if "## Sources Cited" in body or "## Fonti citate" in body:
        return body
    heading = _section_heading("Sources Cited", language)
    lines = [body.rstrip(), "", f"## {heading}", ""]
    if cited_sources:
        for index, source in enumerate(cited_sources, start=1):
            label = source.title or source.domain or source.canonical_url
            lines.append(f"{index}. [{label}]({source.canonical_url})")
    else:
        if language.startswith("it"):
            lines.append("- Nessuna fonte citata supporta conclusioni verificate.")
        else:
            lines.append("- No cited sources support verified conclusions.")
    return "\n".join(lines).strip() + "\n"


@traceable(name="phase:report", run_type="chain", metadata=REPORT_V1.trace_metadata())
def generate_report(
    store: ResearchStore,
    settings: Settings,
    run_id: uuid.UUID,
    *,
    revision_notes: str = "",
) -> uuid.UUID:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"ResearchRun {run_id} not found")

    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    research = contract_from_snapshot(snapshot)
    report_spec = report_contract_from_snapshot(snapshot)
    if research is None:
        from deepscout_core.domain.schemas import PlannerOutput, PlannerQuestion

        planner_stub = PlannerOutput(
            approach="",
            success_criteria=run.goal,
            questions=[
                PlannerQuestion(text=item.text, priority=3) for item in store.list_questions(run_id)
            ],
        )
        research = build_research_contract(
            goal=run.goal,
            planner=planner_stub,
            output_language=run.output_language,
        )
    if report_spec is None:
        report_spec = derive_report_contract(research)

    coverage = evaluate_coverage(store, run_id, research)
    store.merge_config_snapshot(run_id, {"coverage_map": coverage.model_dump(mode="json")})
    language = research.output_language or run.output_language or "en"

    existing = store.get_report(run_id)
    if existing is not None:
        _archive_report_revision(store, run_id, existing)

    synthesized = synthesize_goal_conditioned_report(
        store,
        settings,
        run_id,
        research=research,
        report_spec=report_spec,
        revision_notes=revision_notes,
    )
    if synthesized is not None:
        cited_sources, cited_evidence_ids = _evidence_ids_for_claims(
            store, run_id, synthesized.cited_claim_ids
        )
        body = _append_sources_cited(synthesized.body_markdown, cited_sources, language)
        title = synthesized.title or report_spec.title
        if cited_evidence_ids:
            report = store.save_report(
                run_id,
                ReportWrite(
                    title=title,
                    body_markdown=body,
                    cited_evidence_ids=cited_evidence_ids[:50],
                ),
            )
            return report.id
        report = store.save_report_draft(run_id, title=title, body_markdown=body)
        return report.id

    decision = store.get_decision(run_id)
    contradictions = store.list_contradictions(run_id)

    cited_sources, cited_evidence_ids = _collect_cited_sources(store, run_id)

    title = report_spec.title
    lines = [f"# {title}", ""]

    exec_heading = _section_heading("Executive Summary", language)
    lines.extend([f"## {exec_heading}", ""])
    if decision is not None:
        lines.append(decision.recommendation.strip())
        lines.append("")
        if decision.rationale.strip():
            lines.append(decision.rationale.strip())
    else:
        supported = [
            entry
            for entry in coverage.entries
            if entry.status == RequirementCoverageStatus.SUPPORTED
        ]
        if supported:
            if language.startswith("it"):
                lines.append(
                    "La ricerca ha prodotto evidenze verificate su parte della richiesta. "
                    "Vedi l'analisi e le limitazioni per i dettagli."
                )
            else:
                lines.append(
                    "Research produced verified evidence for part of the request. "
                    "See analysis and limitations for detail."
                )
        else:
            if language.startswith("it"):
                lines.append(
                    "Evidenza verificata insufficiente per una raccomandazione completa. "
                    "Le sezioni seguenti spiegano cosa resta non supportato."
                )
            else:
                lines.append(
                    "Insufficient verified evidence for a complete recommendation. "
                    "The sections below explain what remains unsupported."
                )

    if report_spec.include_questions_answered and research.user_facing_questions:
        qa_heading = _section_heading("Questions Answered", language)
        lines.extend(["", f"## {qa_heading}"])
        for question in research.user_facing_questions[:8]:
            lines.append(f"### {question}")
            related = [
                entry
                for entry in coverage.entries
                if entry.status
                in {
                    RequirementCoverageStatus.SUPPORTED,
                    RequirementCoverageStatus.PARTIAL,
                }
            ]
            if related:
                if language.startswith("it"):
                    lines.append("- Risposta parziale o completa disponibile nell'analisi sottostante.")
                else:
                    lines.append("- A partial or complete answer is available in the analysis below.")
            else:
                if language.startswith("it"):
                    lines.append("- Evidenza verificata insufficiente per questa domanda.")
                else:
                    lines.append("- Insufficient verified evidence for this question.")
            lines.append("")

    analysis_heading = _section_heading("Analysis", language)
    lines.extend(["", f"## {analysis_heading}", ""])
    claims = [
        claim
        for claim in store.list_claims(run_id)
        if claim.verification_status
        in {
            ClaimVerificationStatus.VERIFIED,
            ClaimVerificationStatus.PARTIALLY_VERIFIED,
        }
    ]
    if claims:
        for index, claim in enumerate(claims[:12], start=1):
            lines.append(f"{index}. {claim.statement.strip()}")
    elif language.startswith("it"):
        lines.append("Nessuna affermazione verificata disponibile per l'analisi.")
    else:
        lines.append("No verified claims available for analysis.")

    if report_spec.include_chronology:
        timeline_heading = _section_heading("Timeline and Applicability", language)
        lines.extend(["", f"## {timeline_heading}", ""])
        timeline_claims = [
            claim.statement.strip()
            for claim in claims
            if any(
                token in claim.statement.casefold()
                for token in ("2024", "2025", "2026", "2027", "applicable", "enforcement", "transitional")
            )
        ][:8]
        if timeline_claims:
            for item in timeline_claims:
                lines.append(f"- {item}")
        elif language.startswith("it"):
            lines.append("- Nessuna cronologia verificata estratta dalle fonti ammesse.")
        else:
            lines.append("- No verified chronology extracted from admissible sources.")

    if report_spec.include_comparisons and research.required_comparisons:
        comparison_heading = _section_heading("Comparison", language)
        lines.extend(["", f"## {comparison_heading}", ""])
        for item in research.required_comparisons:
            lines.append(f"- {item}")

    if contradictions:
        if language.startswith("it"):
            lines.extend(["", "## Conflitti e incertezze"])
        else:
            lines.extend(["", "## Conflicts and Uncertainty"])
        for row_item in contradictions[:8]:
            lines.append(f"- {row_item.description[:400]}")

    lines.extend(_render_coverage_section(research, coverage, language))

    if report_spec.include_sources_cited:
        sources_heading = _section_heading("Sources Cited", language)
        lines.extend(["", f"## {sources_heading}", ""])
        if cited_sources:
            for index, source in enumerate(cited_sources, start=1):
                label = source.title or source.domain or source.canonical_url
                lines.append(f"{index}. [{label}]({source.canonical_url})")
        elif language.startswith("it"):
            lines.append("- Nessuna fonte citata supporta conclusioni verificate.")
        else:
            lines.append("- No cited sources support verified conclusions.")

    body = "\n".join(lines).strip() + "\n"
    if cited_evidence_ids:
        report = store.save_report(
            run_id,
            ReportWrite(
                title=title,
                body_markdown=body,
                cited_evidence_ids=cited_evidence_ids[:50],
            ),
        )
        return report.id

    report = store.save_report_draft(
        run_id,
        title=title,
        body_markdown=body,
    )
    return report.id
