"""Goal-conditioned LLM report synthesis from curated verified evidence."""

from __future__ import annotations

import json
import uuid

from deepscout_core.domain.contracts import ReportContract, ResearchContract
from deepscout_core.domain.enums import AgentRole, ClaimVerificationStatus, ResearchPhase
from deepscout_core.domain.schemas import ReportSynthesisOutput
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_providers.config import application_retry_policy
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import (
    contract_from_snapshot,
    report_contract_from_snapshot,
)
from deepscout_research.contracts.source_authority import (
    classify_source_authority,
    is_source_admissible,
)
from deepscout_research.prompts import REPORT_V1, compose_system_message
from deepscout_research.retry import run_with_retry
from deepscout_research.routing.model_router import ModelRouter
from deepscout_research.usage.recorder import langsmith_metadata, record_model_usage

_LEAK_FORBIDDEN = (
    "coverage_state",
    "ResearchContract",
    "ReportContract",
    "critic_result",
    "task_key",
    "worker_id",
    "answer provided",
)


def _verified_claims(store: ResearchStore, run_id: uuid.UUID):
    return [
        claim
        for claim in store.list_claims(run_id)
        if claim.verification_status
        in {
            ClaimVerificationStatus.VERIFIED,
            ClaimVerificationStatus.PARTIALLY_VERIFIED,
        }
    ]


def build_synthesis_context(
    store: ResearchStore,
    run_id: uuid.UUID,
    *,
    research: ResearchContract,
    report_spec: ReportContract,
) -> dict:
    coverage = evaluate_coverage(store, run_id, research)
    claims = _verified_claims(store, run_id)
    evidence = store.list_evidence(run_id)
    evidence_by_claim = {item.claim_id: item for item in evidence}
    sources_by_id = {source.id: source for source in store.list_sources(run_id)}

    claim_blocks: list[dict] = []
    for claim in claims[:20]:
        ev = evidence_by_claim.get(claim.id)
        source = sources_by_id.get(claim.source_id) if claim.source_id else None
        if source is not None:
            row = store.get_run_row(run_id)
            contract = contract_from_snapshot(row.config_snapshot if row else None)
            prefs = store.list_source_preferences(run_id)
            admissible, _ = is_source_admissible(
                source.canonical_url,
                contract=contract,
                preferences=prefs,
                title=source.title or "",
            )
            if not admissible:
                continue
        authority = (
            classify_source_authority(
                url=source.canonical_url,
                title=source.title or "",
            ).model_dump(mode="json")
            if source
            else {}
        )
        claim_blocks.append(
            {
                "claim_id": str(claim.id),
                "statement": claim.statement[:1200],
                "verification_status": claim.verification_status.value,
                "evidence_quote": (ev.quote[:1200] if ev else ""),
                "source_title": (source.title if source else ""),
                "source_url": (source.canonical_url if source else ""),
                "source_authority": authority,
            }
        )

    contradictions = [
        {"description": row.description[:500]}
        for row in store.list_contradictions(run_id)[:8]
    ]
    return {
        "primary_question": research.primary_question,
        "output_language": research.output_language,
        "report_type": report_spec.report_type.value,
        "required_sections": [section.heading for section in report_spec.sections],
        "requirements": [
            {
                "id": req.requirement_id,
                "text": req.text,
                "critical": req.critical,
                "status": next(
                    (
                        entry.status.value
                        for entry in coverage.entries
                        if entry.requirement_id == req.requirement_id
                    ),
                    "unknown",
                ),
            }
            for req in research.requirements[:15]
        ],
        "verified_claims": claim_blocks,
        "contradictions": contradictions,
        "unresolved_requirements": coverage.critical_unresolved[:10],
    }


def _sanitize_report_body(body: str) -> str:
    cleaned = body.strip()
    for token in _LEAK_FORBIDDEN:
        if token in cleaned:
            cleaned = cleaned.replace(token, "")
    return cleaned.strip() + "\n"


@traceable(name="phase:report_synthesis", run_type="chain", metadata=REPORT_V1.trace_metadata())
def synthesize_goal_conditioned_report(
    store: ResearchStore,
    settings: Settings,
    run_id: uuid.UUID,
    *,
    research: ResearchContract | None = None,
    report_spec: ReportContract | None = None,
    revision_notes: str = "",
) -> ReportSynthesisOutput | None:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"ResearchRun {run_id} not found")
    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    research = research or contract_from_snapshot(snapshot)
    report_spec = report_spec or report_contract_from_snapshot(snapshot)
    if research is None or report_spec is None:
        return None

    context = build_synthesis_context(
        store,
        run_id,
        research=research,
        report_spec=report_spec,
    )
    if not context["verified_claims"]:
        return None

    language = research.output_language or run.output_language or "en"
    section_list = ", ".join(context["required_sections"])
    instructions = (
        f"Write the final research report in {language}. "
        f"Report type: {report_spec.report_type.value}. "
        f"Required sections (use these headings, localized to {language}): {section_list}. "
        "Use ONLY verified claims and evidence quotes provided. "
        "Number citations [1], [2] matching source order in Sources Cited. "
        "For PARTIAL or unresolved requirements, explain precisely what is missing. "
        "Never emit internal task text, planner objectives, task keys, or debug scaffolding. "
        "Do not invent numbers not supported by evidence quotes. "
        "Distinguish source-reported facts from any calculated values you derive. "
        "If evidence is partial, produce a useful partial answer — do not collapse to "
        "INSUFFICIENT_EVIDENCE for the entire report."
    )
    if revision_notes:
        instructions += f" Revision notes: {revision_notes[:1500]}"

    try:
        router = ModelRouter(settings)
        model, selection = router.build_chat_model(AgentRole.REPORT)
    except (ValueError, LookupError):
        return None
    structured = model.with_structured_output(ReportSynthesisOutput, include_raw=True)
    trace_meta = langsmith_metadata(prompt=REPORT_V1, selection=selection, run_id=run_id)

    def _invoke() -> object:
        return structured.invoke(
            [
                SystemMessage(content=compose_system_message(REPORT_V1)),
                HumanMessage(
                    content=instructions
                    + "\n\nSTRUCTURED_RESEARCH_DATA:\n"
                    + json.dumps(context, ensure_ascii=False)[:14000]
                ),
            ],
            config={"metadata": trace_meta},
        )

    raw_result = run_with_retry(_invoke, policy=application_retry_policy(settings))
    if isinstance(raw_result, dict):
        parsed = raw_result.get("parsed")
        raw_message = raw_result.get("raw")
    else:
        parsed = raw_result
        raw_message = None
    if raw_message is not None:
        record_model_usage(
            store,
            settings,
            message=raw_message,
            run_id=run_id,
            phase=ResearchPhase.REPORT,
            role=AgentRole.REPORT,
            selection=selection,
            prompt=REPORT_V1,
        )
    if not isinstance(parsed, ReportSynthesisOutput):
        parsed = ReportSynthesisOutput.model_validate(parsed)
    parsed.body_markdown = _sanitize_report_body(parsed.body_markdown)
    return parsed
