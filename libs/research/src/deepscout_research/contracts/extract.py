"""Contract extraction and derivation from user goal and planner output."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import (
    AnswerRequirement,
    EvidenceStandard,
    ReportContract,
    ReportSectionSpec,
    ReportType,
    RequirementKind,
    ResearchContract,
    SourceClass,
    SourceConstraint,
    SourceConstraintMode,
)
from deepscout_core.domain.schemas import PlannerOutput

_TASK_VERB_PREFIXES = (
    "collect",
    "gather",
    "search",
    "find",
    "retrieve",
    "analyze",
    "analyse",
    "synthesize",
    "synthesise",
    "compile",
    "review sources",
    "identify sources",
    "raccolta",
    "cerca",
    "analizza",
    "sintetizza",
)

_COMPARISON_HINTS = ("compare", "versus", "vs", "confronta", "rispetto a")
_REGULATORY_HINTS = (
    "regulation",
    "obligation",
    "compliance",
    "legal",
    "law",
    "act",
    "directive",
    "normativa",
    "obbligh",
    "regolamento",
)
_SCIENTIFIC_HINTS = (
    "study",
    "peer-reviewed",
    "peer reviewed",
    "lifecycle",
    "emissions",
    "methodology",
    "quantify",
    "quantitative",
    "studi",
    "emissioni",
)
_TRADEOFF_HINTS = ("tradeoff", "trade-off", "trade off", "vs", "versus", "compared to")
_TIMELINE_HINTS = ("timeline", "when", "applicable", "enforcement", "transitional", "cronologia")
_ONLY_SOURCE_PATTERNS: tuple[tuple[re.Pattern[str], list[str], list[SourceClass]], ...] = (
    (
        re.compile(
            r"\b(only|solely|exclusively|just)\b.{0,40}\b(official)\b.{0,60}\b(eu|european union)\b",
            re.I,
        ),
        ["europa.eu", "eur-lex.europa.eu", "ec.europa.eu", "commission.europa.eu", "digital-strategy.ec.europa.eu", "ai-office.ec.europa.eu"],
        [SourceClass.OFFICIAL_INSTITUTIONAL, SourceClass.PRIMARY_LEGISLATION],
    ),
    (
        re.compile(
            r"\b(solo|solamente|esclusivamente)\b.{0,80}"
            r"\b(fonti\s+)?(istituzional\w*|ufficial\w*).{0,50}\b(dell[''])?(ue|eu|unione europea)\b",
            re.I,
        ),
        ["europa.eu", "eur-lex.europa.eu", "ec.europa.eu", "commission.europa.eu", "digital-strategy.ec.europa.eu", "ai-office.ec.europa.eu"],
        [SourceClass.OFFICIAL_INSTITUTIONAL, SourceClass.PRIMARY_LEGISLATION],
    ),
    (
        re.compile(
            r"\b(utilizza|use|using)\b.{0,30}\b(esclusivamente|only|solely)\b.{0,80}"
            r"\b(ue|eu|unione europea|european union)\b",
            re.I,
        ),
        ["europa.eu", "eur-lex.europa.eu", "ec.europa.eu", "commission.europa.eu", "digital-strategy.ec.europa.eu", "ai-office.ec.europa.eu"],
        [SourceClass.OFFICIAL_INSTITUTIONAL, SourceClass.PRIMARY_LEGISLATION],
    ),
    (
        re.compile(r"\bonly\b.{0,30}\bofficial\b.{0,30}\bgovernment\b", re.I),
        [],
        [SourceClass.OFFICIAL_INSTITUTIONAL, SourceClass.GOVERNMENT_STATISTICS],
    ),
)

_PREFER_SOURCE_PATTERNS: tuple[tuple[re.Pattern[str], list[str]], ...] = (
    (re.compile(r"\bprefer\b[^.]{0,120}", re.I), []),
    (re.compile(r"\bprioriti[sz]e\b[^.]{0,120}", re.I), []),
    (re.compile(r"\bpreferire\b[^.]{0,120}", re.I), []),
)

_CLASS_KEYWORDS: tuple[tuple[str, SourceClass], ...] = (
    ("peer-reviewed", SourceClass.PEER_REVIEWED),
    ("peer reviewed", SourceClass.PEER_REVIEWED),
    ("national lab", SourceClass.RESEARCH_BODY),
    ("doe", SourceClass.RESEARCH_BODY),
    ("icct", SourceClass.RESEARCH_BODY),
    ("iea", SourceClass.RESEARCH_BODY),
    ("eur-lex", SourceClass.PRIMARY_LEGISLATION),
    ("official", SourceClass.OFFICIAL_INSTITUTIONAL),
    ("regulator", SourceClass.REGULATOR),
    ("financial filing", SourceClass.FINANCIAL_FILING),
    ("sec filing", SourceClass.FINANCIAL_FILING),
)


def _looks_like_internal_task(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return True
    first = lowered.split()[0] if lowered.split() else ""
    if first in _TASK_VERB_PREFIXES:
        return True
    if lowered.startswith("task "):
        return True
    return False


def _user_facing_questions(goal: str, planner: PlannerOutput) -> list[str]:
    candidates: list[str] = []
    for question in planner.questions:
        text = question.text.strip()
        if text and not _looks_like_internal_task(text):
            candidates.append(text)
    if candidates:
        return candidates[:10]
    sentences = [part.strip() for part in re.split(r"[?\n;]+", goal) if part.strip()]
    out: list[str] = []
    for sentence in sentences:
        if _looks_like_internal_task(sentence):
            continue
        if len(sentence) < 12:
            continue
        out.append(sentence if sentence.endswith("?") else f"{sentence}?")
        if len(out) >= 8:
            break
    if out:
        return out
    return [goal.strip()[:500]]


def _infer_report_type(goal: str, requirements: list[AnswerRequirement]) -> ReportType:
    lowered = goal.casefold()
    kinds = {item.kind for item in requirements}
    if any(h in lowered for h in _REGULATORY_HINTS) or RequirementKind.TIMELINE in kinds:
        return ReportType.REGULATORY_ANALYSIS
    if RequirementKind.COMPARISON in kinds or any(h in lowered for h in _COMPARISON_HINTS):
        if any(h in lowered for h in _SCIENTIFIC_HINTS):
            return ReportType.SCIENTIFIC_REVIEW
        return ReportType.COMPARISON
    if RequirementKind.TRADEOFF in kinds or any(h in lowered for h in _TRADEOFF_HINTS):
        return ReportType.TECHNICAL_TRADEOFF
    if any(h in lowered for h in _SCIENTIFIC_HINTS):
        return ReportType.SCIENTIFIC_REVIEW
    if "market" in lowered or "competitor" in lowered:
        return ReportType.MARKET_ANALYSIS
    if RequirementKind.DEPENDENCY in kinds:
        return ReportType.MULTI_HOP
    if any(h in lowered for h in _TIMELINE_HINTS):
        return ReportType.TEMPORAL_UPDATE
    if len(requirements) <= 2 and not any(
        item.quantification_required or item.kind != RequirementKind.FACT for item in requirements
    ):
        return ReportType.FACT_FINDING
    return ReportType.GENERAL_RESEARCH


def _extract_source_constraints(goal: str) -> list[SourceConstraint]:
    constraints: list[SourceConstraint] = []
    for pattern, domains, classes in _ONLY_SOURCE_PATTERNS:
        if pattern.search(goal):
            values = domains or [item.value for item in classes]
            constraints.append(
                SourceConstraint(
                    mode=SourceConstraintMode.ONLY,
                    scope="domain" if domains else "class",
                    values=values,
                    reason="User requested official-only sources",
                )
            )
            break
    for pattern, _ in _PREFER_SOURCE_PATTERNS:
        match = pattern.search(goal)
        if not match:
            continue
        fragment = match.group(0)
        names = re.findall(r"[A-Z]{2,}(?:\s[A-Z][a-z]+)?|[A-Z][a-z]+(?:\s[A-Z][a-z]+)?", fragment)
        if names:
            constraints.append(
                SourceConstraint(
                    mode=SourceConstraintMode.PREFER,
                    scope="publisher",
                    values=[name.strip() for name in names[:8]],
                    reason="User preferred sources",
                )
            )
    return constraints


def _preferred_classes(goal: str) -> list[SourceClass]:
    lowered = goal.casefold()
    found: list[SourceClass] = []
    for keyword, source_class in _CLASS_KEYWORDS:
        if keyword in lowered and source_class not in found:
            found.append(source_class)
    return found


def _requirement_from_text(
    requirement_id: str,
    text: str,
    *,
    kind: RequirementKind = RequirementKind.FACT,
    critical: bool = True,
    quantification_required: bool = False,
    depends_on: list[str] | None = None,
) -> AnswerRequirement:
    return AnswerRequirement(
        requirement_id=requirement_id,
        text=text.strip()[:2000],
        kind=kind,
        critical=critical,
        quantification_required=quantification_required,
        depends_on=list(depends_on or []),
    )


def _decompose_requirements(goal: str, planner: PlannerOutput) -> list[AnswerRequirement]:
    requirements: list[AnswerRequirement] = []
    lowered = goal.casefold()

    requirements.append(
        _requirement_from_text("R0", f"Answer the primary research objective: {goal[:500]}", critical=True)
    )

    if any(h in lowered for h in _COMPARISON_HINTS):
        requirements.append(
            _requirement_from_text(
                "R_compare",
                "Provide a direct comparison across the requested subjects or options",
                kind=RequirementKind.COMPARISON,
                critical=True,
            )
        )

    if any(word in lowered for word in ("quantify", "quantitative", "number", "estimate", "break-even", "break even")):
        requirements.append(
            _requirement_from_text(
                "R_quant",
                "Provide quantitative estimates where published sources allow",
                kind=RequirementKind.QUANTIFICATION,
                critical=True,
                quantification_required=True,
            )
        )

    if any(h in lowered for h in _REGULATORY_HINTS):
        if any(
            word in lowered
            for word in (
                "applicable",
                "transitional",
                "already",
                "future",
                "già",
                "successiv",
                "transitori",
                "distingu",
                "decorrenza",
            )
        ):
            requirements.append(
                _requirement_from_text(
                    "R_reg_now",
                    "Identify obligations already applicable or in force before or during the requested period",
                    kind=RequirementKind.DISTINCTION,
                    critical=True,
                )
            )
            requirements.append(
                _requirement_from_text(
                    "R_reg_later",
                    "Identify obligations with later, transitional, or future application dates",
                    kind=RequirementKind.DISTINCTION,
                    critical=True,
                )
            )
            requirements.append(
                _requirement_from_text(
                    "R_reg_apply",
                    "Distinguish obligations already applicable from future or transitional requirements",
                    kind=RequirementKind.DISTINCTION,
                    critical=True,
                )
            )
        if any(
            word in lowered
            for word in (
                "enforcement",
                "timing",
                "timeline",
                "transitional",
                "cronologia",
                "decorrenza",
            )
        ):
            requirements.append(
                _requirement_from_text(
                    "R_reg_time",
                    "Explain enforcement timing and transitional rules where relevant",
                    kind=RequirementKind.TIMELINE,
                    critical=True,
                )
            )

    if any(h in lowered for h in _TIMELINE_HINTS):
        requirements.append(
            _requirement_from_text(
                "R_timeline",
                "Provide a chronology of key dates and applicability",
                kind=RequirementKind.TIMELINE,
                critical=True,
            )
        )

    if "then" in lowered or "after identifying" in lowered or "quindi" in lowered:
        requirements.append(
            _requirement_from_text(
                "R_dep",
                "Resolve dependent sub-questions in order before downstream conclusions",
                kind=RequirementKind.DEPENDENCY,
                critical=True,
            )
        )

    if "president" in lowered or "presidente" in lowered:
        requirements.append(
            _requirement_from_text(
                "R_president",
                "Identify the current office-holder from authoritative sources",
                kind=RequirementKind.FACT,
                critical=True,
            )
        )
        if any(token in lowered for token in ("gpai", "modelli di ia", "general purpose", "general-purpose")):
            requirements.append(
                _requirement_from_text(
                    "R_gpai_guidance",
                    "Document GPAI provider guidance published by the European Commission for 2026",
                    kind=RequirementKind.FACT,
                    critical=True,
                    depends_on=["R_president"],
                )
            )

    if any(h in lowered for h in ("why", "methodology", "methodological", "drivers", "explain why")):
        requirements.append(
            _requirement_from_text(
                "R_method",
                "Explain methodological or structural reasons behind differences in findings",
                kind=RequirementKind.METHODOLOGY,
                critical=False,
            )
        )

    if any(h in lowered for h in _TRADEOFF_HINTS):
        requirements.append(
            _requirement_from_text(
                "R_tradeoff",
                "Explain practical trade-offs across the requested dimensions",
                kind=RequirementKind.TRADEOFF,
                critical=True,
            )
        )

    if planner.success_criteria.strip():
        requirements.append(
            _requirement_from_text(
                "R_success",
                planner.success_criteria.strip()[:2000],
                kind=RequirementKind.SYNTHESIS,
                critical=False,
            )
        )

    # Deduplicate by text
    seen: set[str] = set()
    unique: list[AnswerRequirement] = []
    for item in requirements:
        key = item.text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:25]


def _evidence_standard(goal: str, preferred: list[SourceClass]) -> EvidenceStandard:
    lowered = goal.casefold()
    if SourceClass.PEER_REVIEWED in preferred or "peer-reviewed" in lowered or "peer reviewed" in lowered:
        return EvidenceStandard.PEER_REVIEWED
    if SourceClass.OFFICIAL_INSTITUTIONAL in preferred or "official" in lowered:
        return EvidenceStandard.AUTHORITATIVE
    return EvidenceStandard.CREDIBLE


def build_research_contract(
    *,
    goal: str,
    planner: PlannerOutput,
    output_language: str = "en",
) -> ResearchContract:
    requirements = _decompose_requirements(goal, planner)
    preferred = _preferred_classes(goal)
    constraints = _extract_source_constraints(goal)
    required_classes: list[SourceClass] = []
    for constraint in constraints:
        if constraint.mode == SourceConstraintMode.ONLY and constraint.scope == "class":
            for value in constraint.values:
                try:
                    required_classes.append(SourceClass(value))
                except ValueError:
                    continue
    distinctions: list[str] = []
    if any("applicable" in goal.casefold() for _ in [0]):
        distinctions.append("already_applicable_vs_future")
    if "transitional" in goal.casefold():
        distinctions.append("transitional_requirements")
    comparisons: list[str] = []
    for match in re.finditer(r"\b(\w+)\s+vs\.?\s+(\w+)\b", goal, re.I):
        comparisons.append(f"{match.group(1)} vs {match.group(2)}")
    quant: list[str] = []
    if any(word in goal.casefold() for word in ("quantify", "number", "estimate", "break-even", "break even")):
        quant.append("numeric_estimates_where_available")

    return ResearchContract(
        primary_question=goal.strip(),
        user_intent=planner.approach.strip()[:4000],
        output_language=output_language,
        evidence_standard=_evidence_standard(goal, preferred),
        requirements=requirements,
        source_constraints=constraints,
        preferred_source_classes=preferred,
        required_source_classes=required_classes,
        geography=[],
        required_distinctions=distinctions,
        required_comparisons=comparisons[:5],
        required_quantification=quant,
        required_timeframes=[],
        uncertainty_requirements=["explain_missing_evidence_precisely"],
        user_facing_questions=_user_facing_questions(goal, planner),
    )


def derive_report_contract(research: ResearchContract) -> ReportContract:
    report_type = _infer_report_type(research.primary_question, research.requirements)
    title = research.primary_question.strip()[:200]
    if len(research.primary_question) > 200:
        title = research.primary_question.strip()[:197] + "..."

    sections: list[ReportSectionSpec] = [
        ReportSectionSpec(section_id="executive_summary", heading="Executive Summary", required=True),
        ReportSectionSpec(section_id="analysis", heading="Analysis", required=True),
    ]
    include_chronology = report_type in {
        ReportType.REGULATORY_ANALYSIS,
        ReportType.TEMPORAL_UPDATE,
    }
    include_comparisons = report_type in {
        ReportType.COMPARISON,
        ReportType.SCIENTIFIC_REVIEW,
        ReportType.TECHNICAL_TRADEOFF,
        ReportType.MARKET_ANALYSIS,
    }
    include_quant = any(item.quantification_required for item in research.requirements) or report_type in {
        ReportType.SCIENTIFIC_REVIEW,
        ReportType.COMPARISON,
        ReportType.TECHNICAL_TRADEOFF,
    }
    if include_chronology:
        sections.append(
            ReportSectionSpec(section_id="timeline", heading="Timeline and Applicability", required=True)
        )
    if include_comparisons:
        sections.append(
            ReportSectionSpec(section_id="comparison", heading="Comparison", required=True)
        )
    if include_quant:
        sections.append(
            ReportSectionSpec(
                section_id="quantitative_results",
                heading="Quantitative Results",
                required=any(item.quantification_required for item in research.requirements),
            )
        )
    sections.extend(
        [
            ReportSectionSpec(section_id="limitations", heading="Limitations and Uncertainty", required=True),
            ReportSectionSpec(section_id="sources_cited", heading="Sources Cited", required=True),
        ]
    )
    return ReportContract(
        report_type=report_type,
        title=title,
        executive_summary_required=True,
        sections=sections,
        include_chronology=include_chronology,
        include_comparisons=include_comparisons,
        include_quantitative_results=include_quant,
        include_uncertainty_section=True,
        include_limitations_section=True,
        include_sources_cited=True,
        include_sources_consulted=False,
        include_questions_answered=bool(research.user_facing_questions)
        and report_type in {ReportType.FACT_FINDING, ReportType.MULTI_HOP},
    )


def contract_from_snapshot(snapshot: dict | None) -> ResearchContract | None:
    if not snapshot:
        return None
    raw = snapshot.get("research_contract")
    if not isinstance(raw, dict):
        return None
    try:
        return ResearchContract.model_validate(raw)
    except Exception:
        return None


def report_contract_from_snapshot(snapshot: dict | None) -> ReportContract | None:
    if not snapshot:
        return None
    raw = snapshot.get("report_contract")
    if not isinstance(raw, dict):
        return None
    try:
        return ReportContract.model_validate(raw)
    except Exception:
        return None
