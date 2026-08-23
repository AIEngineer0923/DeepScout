"""Contract extraction and derivation from user goal and planner output."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import (
    AnswerRequirement,
    EvidenceStandard,
    EvidenceType,
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
_QUANTIFICATION_HINTS = (
    "quantif",
    "quantitative",
    "number",
    "numeric",
    "percentage",
    "percent",
    "estimate",
    "measurement",
    "misur",
    "percentual",
    "intervall",
    "density",
    "densità",
)
_DISTINCTION_HINTS = (
    "distinguish",
    "distinguere",
    "distinguendo",
    "differentiate",
    "observed vs",
    "osservat",
    "model/prevision",
)
_METHODOLOGY_HINTS = (
    "methodolog",
    "metodolog",
    "sample",
    "campione",
    "study limitations",
    "limiti dello studio",
    "conflicting studies",
    "studi autorevoli",
)
_SOURCE_POLICY_HINTS = (
    "prioritize",
    "priorità",
    "prefer",
    "peer-reviewed",
    "peer reviewed",
    "primary source",
    "fonte originale",
    "fonti secondarie",
    "official sources",
)
_OUTPUT_HINTS = (
    "conclude",
    "concludi",
    "final judgment",
    "giudizio",
    "supported /",
    "insufficient evidence",
    "output format",
)


def _has_regulatory_hint(text: str) -> bool:
    """Match regulatory language without treating substrings like ``practical`` as Acts."""
    lowered = text.casefold()
    return bool(
        re.search(
            r"\b(?:regulation|regulations|obligation|obligations|compliance|legal|law|laws|"
            r"act|acts|directive|directives|regulator|regulators|authority|authorities)\b|"
            r"\b(?:regulat|obbligh|normativ)\w*|\bautorità\b",
            lowered,
        )
    )


_ONLY_SOURCE_PATTERNS: tuple[tuple[re.Pattern[str], list[str], list[SourceClass]], ...] = (
    (
        re.compile(
            r"\b(only|solely|exclusively|just)\b.{0,40}\b(official)\b.{0,60}\b(eu|european union)\b",
            re.I,
        ),
        [
            "europa.eu",
            "eur-lex.europa.eu",
            "ec.europa.eu",
            "commission.europa.eu",
            "digital-strategy.ec.europa.eu",
            "ai-office.ec.europa.eu",
        ],
        [SourceClass.OFFICIAL_INSTITUTIONAL, SourceClass.PRIMARY_LEGISLATION],
    ),
    (
        re.compile(
            r"\b(solo|solamente|esclusivamente)\b.{0,80}"
            r"\b(fonti\s+)?(istituzional\w*|ufficial\w*).{0,50}\b(dell[''])?(ue|eu|unione europea)\b",
            re.I,
        ),
        [
            "europa.eu",
            "eur-lex.europa.eu",
            "ec.europa.eu",
            "commission.europa.eu",
            "digital-strategy.ec.europa.eu",
            "ai-office.ec.europa.eu",
        ],
        [SourceClass.OFFICIAL_INSTITUTIONAL, SourceClass.PRIMARY_LEGISLATION],
    ),
    (
        re.compile(
            r"\b(utilizza|use|using)\b.{0,30}\b(esclusivamente|only|solely)\b.{0,80}"
            r"\b(ue|eu|unione europea|european union)\b",
            re.I,
        ),
        [
            "europa.eu",
            "eur-lex.europa.eu",
            "ec.europa.eu",
            "commission.europa.eu",
            "digital-strategy.ec.europa.eu",
            "ai-office.ec.europa.eu",
        ],
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
    ("original paper", SourceClass.PEER_REVIEWED),
    ("peer-reviewed", SourceClass.PEER_REVIEWED),
    ("peer reviewed", SourceClass.PEER_REVIEWED),
    ("framework documentation", SourceClass.SOFTWARE_VENDOR),
    ("vendor documentation", SourceClass.SOFTWARE_VENDOR),
    ("official documentation", SourceClass.SOFTWARE_VENDOR),
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
    if _has_regulatory_hint(lowered) or RequirementKind.TIMELINE in kinds:
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
    materiality: str = "central",
    comparison_subjects: list[str] | None = None,
    expected_source_classes: list[SourceClass] | None = None,
    required_evidence_types: list[EvidenceType] | None = None,
) -> AnswerRequirement:
    return AnswerRequirement(
        requirement_id=requirement_id,
        text=text.strip()[:2000],
        kind=kind,
        critical=critical,
        materiality=materiality,  # type: ignore[arg-type]
        quantification_required=quantification_required,
        depends_on=list(depends_on or []),
        comparison_subjects=list(comparison_subjects or []),
        expected_source_classes=list(expected_source_classes or []),
        required_evidence_types=list(required_evidence_types or []),
    )


def _material_segments(goal: str, planner: PlannerOutput) -> list[str]:
    """Extract user-authored material clauses without inventing domain concepts."""
    bullet_segments = [
        match.group(1).strip()
        for line in goal.splitlines()
        if (match := re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$", line))
    ]
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", goal)]
    instruction_segments = [
        part
        for part in paragraphs
        if len(part) >= 24
        and any(
            hint in part.casefold()
            for hint in (
                *_DISTINCTION_HINTS,
                *_METHODOLOGY_HINTS,
                *_SOURCE_POLICY_HINTS,
                *_OUTPUT_HINTS,
            )
        )
        and not any(item in part for item in bullet_segments)
    ]
    candidates = bullet_segments + instruction_segments if bullet_segments else []
    if not bullet_segments:
        clauses = [
            re.sub(r"\s+", " ", part).strip()
            for part in re.split(r"(?<=[.!?])\s+|;|\n+", goal)
            if len(part.strip()) >= 20
        ]
        if len(clauses) > 1:
            candidates = clauses
        else:
            candidates = instruction_segments
    if not candidates:
        candidates = [
            question.text.strip()
            for question in planner.questions
            if question.text.strip() and not _looks_like_internal_task(question.text)
        ]
    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        normalized = re.sub(r"\s+", " ", candidate).strip(" -*•\t")
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        out.append(normalized[:2000])
    return out[:24]


def _comparison_subjects(text: str) -> list[str]:
    enumerated = re.search(
        r"\b(?:compare|confronta)\s+(.+?)(?=\s+for\s+(?:a|an|the)\b|"
        r"\s+su\s+(?:ciclo|densit|sicurezza|driver|costo|effett)|"
        r",\s*(?:focusing|evaluat|assess)|[.;]|$)",
        text,
        re.I,
    )
    if enumerated and re.search(r"(?:,\s*|\s+)(?:and|e)\s+", enumerated.group(1), re.I):
        body = re.sub(
            r"^(?:the\s+)?(?:current\s+)?(?:evidence|estimates?)\s+(?:on|of)\s+",
            "",
            enumerated.group(1).strip(),
            flags=re.I,
        )
        parts = [
            part.strip(" ,;:")
            for part in re.split(r"\s*,\s*(?:and\s+)?|\s+(?:and|e)\s+", body)
            if part.strip(" ,;:")
        ]
        if 2 <= len(parts) <= 5:
            return parts
    patterns = (
        r"\b([\w-]{2,40})\s+(?:vs\.?|versus)\s+([\w-]{2,40})\b",
        r"\b(?:compare|confronta)\s+([\w-]{2,40})\s+(?:and|e|con)\s+([\w-]{2,40})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return [match.group(1), match.group(2)]
    relative = re.search(
        r"(.{3,80}?)\s+(?:compared to|rispetto (?:a|ad|all['’]))\s*(.{3,80})", text, re.I
    )
    if relative:
        left = " ".join(relative.group(1).split()[-5:])
        right = " ".join(relative.group(2).split()[:5])
        return [left.strip(" ,.;:"), right.strip(" ,.;:")]
    return []


def _kind_for_text(text: str) -> tuple[RequirementKind, bool]:
    lowered = text.casefold()
    quantification = any(hint in lowered for hint in _QUANTIFICATION_HINTS)
    if any(hint in lowered for hint in _SOURCE_POLICY_HINTS) or re.search(
        r"\b(?:use|using)\s+only\b.{0,100}\bsources?\b", lowered
    ):
        return RequirementKind.SOURCE_POLICY, False
    if re.search(r"\b(?:depend(?:s|ed|ing)?\s+on|in order before)\b", lowered):
        return RequirementKind.DEPENDENCY, False
    if any(hint in lowered for hint in _OUTPUT_HINTS):
        return RequirementKind.OUTPUT_FORMAT, False
    if any(hint in lowered for hint in _METHODOLOGY_HINTS):
        return RequirementKind.METHODOLOGY, quantification
    if any(hint in lowered for hint in _DISTINCTION_HINTS):
        return RequirementKind.DISTINCTION, quantification
    if any(hint in lowered for hint in _COMPARISON_HINTS):
        return RequirementKind.COMPARISON, quantification
    if any(hint in lowered for hint in _TRADEOFF_HINTS) or (
        any(
            token in lowered
            for token in ("pros and cons", "pro e contro", "advantages", "svantaggi")
        )
    ):
        return RequirementKind.TRADEOFF, quantification
    if quantification:
        return RequirementKind.QUANTIFICATION, True
    if (
        any(hint in lowered for hint in _TIMELINE_HINTS)
        or re.search(
            r"\b(?:after|dopo)\s+\d+|\b\d+(?:\s*[+,/]\s*\d+)*\+?\s*(?:years?|anni)\b",
            lowered,
        )
        or (
            len(re.findall(r"\b\d+", lowered)) >= 2
            and any(token in lowered for token in ("recover", "recuper"))
            and any(token in lowered for token in ("year", "anni"))
        )
    ):
        return RequirementKind.TIMELINE, False
    return RequirementKind.FACT, False


def _source_expectations(text: str, kind: RequirementKind) -> list[SourceClass]:
    lowered = text.casefold()
    if kind == RequirementKind.SOURCE_POLICY:
        return []
    if _has_regulatory_hint(lowered):
        return [
            SourceClass.PRIMARY_LEGISLATION,
            SourceClass.REGULATOR,
            SourceClass.OFFICIAL_INSTITUTIONAL,
        ]
    if any(
        token in lowered
        for token in (
            "study",
            "studi",
            "experiment",
            "esperiment",
            "observed",
            "osservat",
            "ecosystem",
            "ecosistema",
            "biodiversity",
            "biodiversità",
            "methodolog",
            "metodolog",
            "model",
        )
    ):
        return [SourceClass.PEER_REVIEWED, SourceClass.RESEARCH_BODY]
    if kind == RequirementKind.QUANTIFICATION:
        return [
            SourceClass.GOVERNMENT_STATISTICS,
            SourceClass.PEER_REVIEWED,
            SourceClass.RESEARCH_BODY,
            SourceClass.FINANCIAL_FILING,
        ]
    if any(
        token in lowered
        for token in ("company", "società", "financial", "earnings", "revenue", "ricavi")
    ):
        return [
            SourceClass.FINANCIAL_FILING,
            SourceClass.GOVERNMENT_STATISTICS,
            SourceClass.RESEARCH_BODY,
            SourceClass.PEER_REVIEWED,
        ]
    if any(token in lowered for token in ("market", "mercato", "supply", "offerta")):
        return [
            SourceClass.GOVERNMENT_STATISTICS,
            SourceClass.RESEARCH_BODY,
            SourceClass.PEER_REVIEWED,
            SourceClass.FINANCIAL_FILING,
        ]
    return []


def _evidence_type_expectations(text: str) -> list[EvidenceType]:
    lowered = text.casefold()
    out: list[EvidenceType] = []
    if any(token in lowered for token in ("experiment", "esperiment", "test")):
        out.append(EvidenceType.EXPERIMENT)
    if any(token in lowered for token in ("observed", "observation", "osservat", "field")):
        out.append(EvidenceType.OBSERVATIONAL)
    if re.search(
        r"\b(?:simulation|simulations|simulated|modelling|modeling|modelled|modeled|"
        r"prediction|predictions|prevision\w*)\b",
        lowered,
    ):
        out.append(EvidenceType.MODEL_SIMULATION)
    if re.search(
        r"\b(?:systematic\s+review|literature\s+review|meta-analysis|meta-analyses|"
        r"revisione\s+sistematica)\b",
        lowered,
    ):
        out.append(EvidenceType.REVIEW_META_ANALYSIS)
    return list(dict.fromkeys(out))


def _decompose_requirements(goal: str, planner: PlannerOutput) -> list[AnswerRequirement]:
    requirements: list[AnswerRequirement] = []
    lowered = goal.casefold()
    segments = _material_segments(goal, planner)

    requirements.append(
        _requirement_from_text(
            "R0",
            f"Answer the primary research objective: {goal[:500]}",
            critical=not bool(segments),
            materiality="central" if not segments else "secondary",
        )
    )

    used_ids = {"R0"}
    generic_index = 1
    for segment in segments:
        kind, quantitative = _kind_for_text(segment)
        preferred_id = None
        if kind == RequirementKind.COMPARISON and "R_compare" not in used_ids:
            preferred_id = "R_compare"
        elif quantitative and "R_quant" not in used_ids:
            preferred_id = "R_quant"
        while f"R{generic_index}" in used_ids:
            generic_index += 1
        requirement_id = preferred_id or f"R{generic_index}"
        used_ids.add(requirement_id)
        generic_index += 1
        is_output = kind == RequirementKind.OUTPUT_FORMAT
        requirements.append(
            _requirement_from_text(
                requirement_id,
                segment,
                kind=kind,
                critical=not is_output,
                materiality="secondary" if is_output else "central",
                quantification_required=quantitative,
                comparison_subjects=_comparison_subjects(segment),
                expected_source_classes=_source_expectations(segment, kind),
                required_evidence_types=_evidence_type_expectations(segment),
            )
        )

    if any(h in lowered for h in _COMPARISON_HINTS) and not any(
        item.kind == RequirementKind.COMPARISON for item in requirements
    ):
        requirements.append(
            _requirement_from_text(
                "R_compare",
                "Provide a direct comparison across the requested subjects or options",
                kind=RequirementKind.COMPARISON,
                critical=True,
                comparison_subjects=_comparison_subjects(goal),
            )
        )

    if _has_regulatory_hint(lowered):
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
        if any(
            token in lowered
            for token in ("gpai", "modelli di ia", "general purpose", "general-purpose")
        ):
            requirements.append(
                _requirement_from_text(
                    "R_gpai_guidance",
                    "Document GPAI provider guidance published by the European Commission for 2026",
                    kind=RequirementKind.FACT,
                    critical=True,
                    depends_on=["R_president"],
                )
            )

    if any(
        h in lowered for h in ("why", "methodology", "methodological", "drivers", "explain why")
    ) and not any(item.kind == RequirementKind.METHODOLOGY for item in requirements):
        requirements.append(
            _requirement_from_text(
                "R_method",
                "Explain methodological or structural reasons behind differences in findings",
                kind=RequirementKind.METHODOLOGY,
                critical=False,
            )
        )

    if any(
        h in lowered
        for h in ("tradeoff", "trade-off", "trade off", "pros and cons", "pro e contro")
    ):
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
                materiality="secondary",
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
    if (
        SourceClass.PEER_REVIEWED in preferred
        or "peer-reviewed" in lowered
        or "peer reviewed" in lowered
    ):
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
    comparisons = [item.text for item in requirements if item.kind == RequirementKind.COMPARISON]
    quant = [item.text for item in requirements if item.quantification_required]
    distinctions.extend(
        item.text for item in requirements if item.kind == RequirementKind.DISTINCTION
    )
    timeframes = [item.text for item in requirements if item.kind == RequirementKind.TIMELINE]

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
        required_timeframes=timeframes[:10],
        uncertainty_requirements=["explain_missing_evidence_precisely"],
        user_facing_questions=_user_facing_questions(goal, planner),
    )


def derive_report_contract(research: ResearchContract) -> ReportContract:
    report_type = _infer_report_type(research.primary_question, research.requirements)
    title = research.primary_question.strip()[:200]
    if len(research.primary_question) > 200:
        title = research.primary_question.strip()[:197] + "..."

    sections: list[ReportSectionSpec] = [
        ReportSectionSpec(
            section_id="executive_summary", heading="Executive Summary", required=True
        ),
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
    include_quant = any(
        item.quantification_required for item in research.requirements
    ) or report_type in {
        ReportType.SCIENTIFIC_REVIEW,
        ReportType.COMPARISON,
        ReportType.TECHNICAL_TRADEOFF,
    }
    if include_chronology:
        sections.append(
            ReportSectionSpec(
                section_id="timeline", heading="Timeline and Applicability", required=True
            )
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
            ReportSectionSpec(
                section_id="limitations", heading="Limitations and Uncertainty", required=True
            ),
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
