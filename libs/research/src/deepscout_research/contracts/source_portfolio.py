"""Requirement-aware source adequacy; authority and relevance remain separate."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from deepscout_core.domain.contracts import (
    AnswerRequirement,
    EvidenceStandard,
    RequirementKind,
    ResearchContract,
    SourceClass,
    SourceKind,
)
from deepscout_core.domain.schemas import SearchResult

from deepscout_research.source_fabric.strategy import SourceStrategy, infer_source_kind

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


_COMMON_PUBLIC_SUFFIXES = {
    "co.uk",
    "com.au",
    "com.br",
    "co.jp",
    "co.nz",
    "com.cn",
}


def source_family(url: str, *, publisher: str = "") -> str:
    """Best-effort publisher family; keeps authority independent from URL count."""
    if publisher.strip():
        return "publisher:" + " ".join(publisher.casefold().split())[:120]
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    suffix2 = ".".join(parts[-2:])
    if suffix2 in _COMMON_PUBLIC_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return suffix2


@dataclass(slots=True)
class SourcePortfolioTracker:
    strategy: SourceStrategy
    urls: set[str] = field(default_factory=set)
    publisher_families: set[str] = field(default_factory=set)
    source_kinds: set[SourceKind] = field(default_factory=set)
    admitted_results: list[SearchResult] = field(default_factory=list)
    query_yields: list[int] = field(default_factory=list)

    def admit(self, result: SearchResult) -> bool:
        if result.url in self.urls:
            return False
        self.urls.add(result.url)
        self.publisher_families.add(source_family(result.url, publisher=result.publisher))
        try:
            kind = SourceKind(result.source_kind)
        except ValueError:
            kind = infer_source_kind(result.url, title=result.title)
        self.source_kinds.add(kind)
        self.admitted_results.append(result)
        return True

    def finish_query(self, admitted_count: int) -> None:
        self.query_yields.append(admitted_count)

    def adequate(self) -> bool:
        return (
            len(self.query_yields) >= self.strategy.minimum_query_families
            and len(self.publisher_families) >= self.strategy.target_independent_publishers
            and len(self.source_kinds) >= self.strategy.target_source_kinds
        )

    def saturated(self) -> bool:
        """Two consecutive zero-yield families indicate bounded low marginal yield."""
        return len(self.query_yields) >= 2 and self.query_yields[-2:] == [0, 0]
