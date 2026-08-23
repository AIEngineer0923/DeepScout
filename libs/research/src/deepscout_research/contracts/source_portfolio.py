"""Requirement-aware source adequacy; authority and relevance remain separate."""

from __future__ import annotations

from deepscout_core.domain.contracts import (
    AnswerRequirement,
    EvidenceStandard,
    RequirementKind,
    ResearchContract,
    SourceClass,
)

_PRIMARY_SCIENTIFIC = {
    SourceClass.PEER_REVIEWED,
    SourceClass.RESEARCH_BODY,
    SourceClass.GOVERNMENT_STATISTICS,
}
_PRIMARY_LEGAL = {
    SourceClass.PRIMARY_LEGISLATION,
    SourceClass.REGULATOR,
    SourceClass.OFFICIAL_INSTITUTIONAL,
}
_PRIMARY_MARKET = {
    SourceClass.FINANCIAL_FILING,
    SourceClass.GOVERNMENT_STATISTICS,
    SourceClass.RESEARCH_BODY,
    SourceClass.PEER_REVIEWED,
}


def adequate_source_classes(
    requirement: AnswerRequirement,
    contract: ResearchContract,
) -> set[SourceClass]:
    if requirement.expected_source_classes:
        return set(requirement.expected_source_classes)
    if requirement.kind == RequirementKind.SOURCE_POLICY:
        return set(contract.required_source_classes or contract.preferred_source_classes)
    lowered = requirement.text.casefold()
    if any(token in lowered for token in ("law", "legal", "regulat", "normativ", "legislation")):
        return set(_PRIMARY_LEGAL)
    if any(token in lowered for token in ("market", "supply", "financial", "mercato", "offerta")):
        return set(_PRIMARY_MARKET)
    if contract.evidence_standard == EvidenceStandard.PEER_REVIEWED:
        return set(_PRIMARY_SCIENTIFIC)
    if contract.evidence_standard == EvidenceStandard.AUTHORITATIVE:
        return set(_PRIMARY_SCIENTIFIC | _PRIMARY_LEGAL | _PRIMARY_MARKET)
    return set()


def source_portfolio_is_adequate(
    requirement: AnswerRequirement,
    contract: ResearchContract,
    source_classes: set[SourceClass],
) -> bool:
    expected = adequate_source_classes(requirement, contract)
    if not expected:
        return bool(source_classes) or requirement.kind in {
            RequirementKind.OUTPUT_FORMAT,
            RequirementKind.SYNTHESIS,
        }
    return bool(expected & source_classes)
