"""Goal-conditioned source strategy and query-family planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from deepscout_core.domain.contracts import (
    RequirementKind,
    ResearchContract,
    SourceClass,
    SourceKind,
)


class QueryStrategy(StrEnum):
    GENERAL = "general"
    EXACT = "exact"
    PRIMARY = "primary"
    DATA = "data"
    RECENT = "recent"
    INDEPENDENT = "independent"
    COMMUNITY = "community"
    ACADEMIC = "academic"
    CODE = "code"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    query: str
    query_language: str = "und"
    max_results: int = 5
    strategy: QueryStrategy = QueryStrategy.GENERAL
    source_kinds: frozenset[SourceKind] = frozenset()
    freshness_days: int | None = None
    topic: str | None = None


@dataclass(frozen=True, slots=True)
class SourceStrategy:
    requested_kinds: frozenset[SourceKind]
    query_families: tuple[QueryStrategy, ...]
    target_independent_publishers: int
    target_source_kinds: int
    contradiction_search: bool
    minimum_query_families: int


_COMMUNITY_HOSTS = {
    "reddit.com",
    "news.ycombinator.com",
    "stackoverflow.com",
    "stackexchange.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "instagram.com",
    "facebook.com",
}
_VIDEO_HOSTS = {"youtube.com", "youtu.be", "vimeo.com"}
_ACADEMIC_HOST_HINTS = (
    "doi.org",
    "openalex.org",
    "arxiv.org",
    "pubmed",
    "ncbi.nlm.nih.gov",
    "semanticscholar.org",
)
_NEWS_HOST_HINTS = ("reuters.com", "apnews.com", "bbc.", "news.")


def _host_matches(host: str, candidates: set[str]) -> bool:
    return any(host == item or host.endswith("." + item) for item in candidates)


def infer_source_kind(url: str, *, title: str = "", content_type: str = "") -> SourceKind:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.casefold()
    lowered = f"{title} {path} {content_type}".casefold()
    if _host_matches(host, _VIDEO_HOSTS):
        return SourceKind.VIDEO
    if _host_matches(host, _COMMUNITY_HOSTS):
        return SourceKind.COMMUNITY_DISCUSSION
    if host == "github.com" or host.endswith(".github.com"):
        if "/releases" in path:
            return SourceKind.TECHNICAL_DOCUMENTATION
        return SourceKind.REPOSITORY
    if any(item in host for item in _ACADEMIC_HOST_HINTS):
        return SourceKind.ACADEMIC_PAPER
    if any(item in host for item in _NEWS_HOST_HINTS):
        return SourceKind.NEWS_ARTICLE
    if "pdf" in content_type.casefold() or path.endswith(".pdf"):
        return SourceKind.DOCUMENT
    if any(token in lowered for token in ("rss", "atom.xml", "/feed")):
        return SourceKind.FEED
    if "json" in content_type.casefold() or "/api/" in path:
        return SourceKind.STRUCTURED_API
    if any(token in lowered for token in ("dataset", "open data", "statistics")):
        return SourceKind.DATASET
    if any(token in host for token in ("docs.", "developer.", "developers.")):
        return SourceKind.TECHNICAL_DOCUMENTATION
    if host.endswith(".gov") or host.endswith(".int") or ".gov." in host:
        return SourceKind.OFFICIAL_SOURCE
    return SourceKind.WEB_PAGE


def plan_source_strategy(
    objective: str,
    contract: ResearchContract | None,
    *,
    research_mode: str | None,
) -> SourceStrategy:
    mode = research_mode or "standard"
    lowered = f"{objective} {contract.primary_question if contract else ''}".casefold()
    kinds: set[SourceKind] = {SourceKind.WEB_PAGE}
    families: list[QueryStrategy] = [QueryStrategy.EXACT, QueryStrategy.PRIMARY]
    requested_classes = set()
    if contract:
        requested_classes.update(contract.required_source_classes)
        requested_classes.update(contract.preferred_source_classes)
    if requested_classes & {
        SourceClass.PEER_REVIEWED,
        SourceClass.RESEARCH_BODY,
    } or re.search(
        r"\b(study|studies|scientific|peer.review|paper|clinical|studio|studi)\b",
        lowered,
    ):
        kinds.add(SourceKind.ACADEMIC_PAPER)
        families.append(QueryStrategy.ACADEMIC)
    if requested_classes & {
        SourceClass.SOFTWARE_VENDOR,
    } or re.search(
        r"\b(github|gitlab|repository|source code|codebase|open.source|software|"
        r"package|framework|sdk|library)\b",
        lowered,
    ):
        kinds.update({SourceKind.REPOSITORY, SourceKind.TECHNICAL_DOCUMENTATION})
        families.append(QueryStrategy.CODE)
    if re.search(r"\b(video|youtube|watch|tutorial|interview|podcast)\b", lowered):
        kinds.add(SourceKind.VIDEO)
        families.append(QueryStrategy.VIDEO)
    if re.search(
        r"\b(user experience|community|forum|reddit|social|sentiment|"
        r"recension|esperienz|opinioni)\b",
        lowered,
    ):
        kinds.add(SourceKind.COMMUNITY_DISCUSSION)
        families.append(QueryStrategy.COMMUNITY)
    if re.search(
        r"\b(current|latest|today|news|recent|202[4-9]|attual|oggi|ultimo|ultime)\b",
        lowered,
    ):
        kinds.add(SourceKind.NEWS_ARTICLE)
        families.append(QueryStrategy.RECENT)
    if re.search(
        r"\b(data|dataset|statistics|quantitative|measurement|statistic|dati|misur)\b",
        lowered,
    ):
        kinds.add(SourceKind.DATASET)
        families.append(QueryStrategy.DATA)
    if any(
        item in requested_classes
        for item in {
            SourceClass.OFFICIAL_INSTITUTIONAL,
            SourceClass.PRIMARY_LEGISLATION,
            SourceClass.REGULATOR,
            SourceClass.GOVERNMENT_STATISTICS,
            SourceClass.FINANCIAL_FILING,
        }
    ):
        kinds.add(SourceKind.OFFICIAL_SOURCE)
    if mode in {"standard", "deep"}:
        families.insert(2, QueryStrategy.INDEPENDENT)
        families.append(QueryStrategy.GENERAL)
    simple_fact = (
        bool(contract)
        and 0 < len(contract.requirements) <= 2
        and all(
            item.kind == RequirementKind.FACT and not item.quantification_required
            for item in contract.requirements
        )
    )
    mode_targets = {
        "quick": (1, 1, False, 1),
        "standard": (2 if simple_fact else 3, min(2, len(kinds)), True, 2),
        "deep": (3 if simple_fact else 4, min(3, len(kinds)), True, 3),
    }
    publishers, source_kinds, contradiction, minimum_families = mode_targets.get(
        mode, mode_targets["standard"]
    )
    return SourceStrategy(
        requested_kinds=frozenset(kinds),
        query_families=tuple(dict.fromkeys(families)),
        target_independent_publishers=publishers,
        target_source_kinds=source_kinds,
        contradiction_search=contradiction,
        minimum_query_families=minimum_families,
    )


def query_suffix(strategy: QueryStrategy) -> str:
    return {
        QueryStrategy.GENERAL: "",
        QueryStrategy.EXACT: "evidence",
        QueryStrategy.PRIMARY: "official primary source",
        QueryStrategy.DATA: "data statistics methodology",
        QueryStrategy.RECENT: "latest current date",
        QueryStrategy.INDEPENDENT: "independent analysis limitations",
        QueryStrategy.COMMUNITY: "community user experience forum",
        QueryStrategy.ACADEMIC: "peer reviewed study DOI methods",
        QueryStrategy.CODE: "GitHub official documentation release",
        QueryStrategy.VIDEO: "video transcript captions",
    }[strategy]


def evidence_role_for_kind(kind: SourceKind) -> str:
    return {
        SourceKind.OFFICIAL_SOURCE: "official_factual_record",
        SourceKind.ACADEMIC_PAPER: "scholarly_evidence",
        SourceKind.NEWS_ARTICLE: "current_reporting",
        SourceKind.VIDEO: "audiovisual_primary_or_commentary",
        SourceKind.COMMUNITY_DISCUSSION: "user_experience_or_sentiment",
        SourceKind.REPOSITORY: "software_implementation",
        SourceKind.TECHNICAL_DOCUMENTATION: "technical_specification",
        SourceKind.DATASET: "quantitative_data",
        SourceKind.DOCUMENT: "documentary_evidence",
        SourceKind.FEED: "freshness_discovery",
        SourceKind.STRUCTURED_API: "structured_factual_record",
        SourceKind.WEB_PAGE: "general_evidence",
        SourceKind.UNKNOWN: "general_evidence",
    }[kind]
