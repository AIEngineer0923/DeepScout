"""Source authority classification and admission policy."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from deepscout_core.domain.contracts import (
    AuthorityClass,
    ResearchContract,
    SourceAdmissionState,
    SourceAuthorityMetadata,
    SourceClass,
    SourceConstraint,
    SourceConstraintMode,
)
from deepscout_core.domain.schemas import SourcePreferenceRead

from deepscout_research.fetch.url_normalize import normalize_source_url
from deepscout_research.source_policy import is_excluded

from deepscout_research.contracts.query_planning import official_source_namespaces

_OFFICIAL_DOMAIN_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".europa.eu",
    ".ec.europa.eu",
    ".int",
    ".edu",
)

_PEER_REVIEW_HINTS = (
    "doi.org",
    "pubmed",
    "arxiv.org",
    "nature.com",
    "sciencedirect.com",
    "springer.com",
    "wiley.com",
    "ieee.org",
    "acs.org",
)

_RESEARCH_BODY_HINTS = (
    "iea.org",
    "icct.org",
    "nrel.gov",
    "energy.gov",
    "ornl.gov",
    "lbl.gov",
    "anl.gov",
)

_NEWS_HINTS = (
    "news.",
    "reuters.com",
    "bbc.",
    "cnn.com",
    "guardian.com",
)

_INDUSTRY_BLOG_HINTS = (
    "medium.com",
    "wordpress.com",
    "blog.",
)


def _domain(url: str) -> str:
    host = urlparse(normalize_source_url(url)).hostname or ""
    return host.removeprefix("www.").lower()


def classify_source_authority(
    *,
    url: str,
    title: str = "",
    publisher: str = "",
) -> SourceAuthorityMetadata:
    domain = _domain(url)
    lowered_title = title.casefold()
    lowered_url = url.casefold()
    source_class = SourceClass.UNKNOWN
    authority = AuthorityClass.UNKNOWN
    institutional = False
    peer_reviewed = False
    official = False
    primary_vs_secondary: str = "unknown"

    if any(domain.endswith(suffix) or suffix.strip(".") in domain for suffix in _OFFICIAL_DOMAIN_SUFFIXES):
        source_class = SourceClass.OFFICIAL_INSTITUTIONAL
        authority = AuthorityClass.PRIMARY
        institutional = True
        official = True
        primary_vs_secondary = "primary"
    elif "eur-lex" in domain:
        source_class = SourceClass.PRIMARY_LEGISLATION
        authority = AuthorityClass.PRIMARY
        official = True
        primary_vs_secondary = "primary"
    elif any(hint in domain for hint in _PEER_REVIEW_HINTS):
        source_class = SourceClass.PEER_REVIEWED
        authority = AuthorityClass.PRIMARY
        peer_reviewed = True
        primary_vs_secondary = "primary"
    elif any(hint in domain for hint in _RESEARCH_BODY_HINTS):
        source_class = SourceClass.RESEARCH_BODY
        authority = AuthorityClass.PRIMARY
        institutional = True
        primary_vs_secondary = "primary"
    elif any(hint in domain for hint in _NEWS_HINTS):
        source_class = SourceClass.NEWS_MEDIA
        authority = AuthorityClass.SECONDARY
        primary_vs_secondary = "secondary"
    elif any(hint in domain for hint in _INDUSTRY_BLOG_HINTS):
        source_class = SourceClass.INDUSTRY_BLOG
        authority = AuthorityClass.TERTIARY
        primary_vs_secondary = "secondary"
    elif re.search(r"\b(whitepaper|datasheet|engineering)\b", lowered_title):
        source_class = SourceClass.MANUFACTURER_ENGINEERING
        authority = AuthorityClass.SECONDARY
        primary_vs_secondary = "secondary"

    if "sec.gov" in domain or "edgar" in lowered_url:
        source_class = SourceClass.FINANCIAL_FILING
        authority = AuthorityClass.PRIMARY
        official = True
        primary_vs_secondary = "primary"

    return SourceAuthorityMetadata(
        source_class=source_class,
        authority_class=authority,
        primary_vs_secondary=primary_vs_secondary,  # type: ignore[arg-type]
        institutional=institutional,
        peer_reviewed=peer_reviewed,
        official=official,
        domain=domain,
        publisher=publisher[:255],
    )


def _matches_domain_constraint(url: str, domains: list[str]) -> bool:
    host = _domain(url)
    for item in domains:
        normalized = item.lower().removeprefix("www.")
        if host == normalized or host.endswith("." + normalized) or normalized in host:
            return True
    return False


def _matches_class_constraint(metadata: SourceAuthorityMetadata, classes: list[str]) -> bool:
    if not classes:
        return True
    return metadata.source_class.value in classes or metadata.authority_class.value in classes


def violates_only_constraint(
    url: str,
    *,
    contract: ResearchContract | None,
    metadata: SourceAuthorityMetadata | None = None,
) -> bool:
    if contract is None:
        return False
    only_constraints = [
        item for item in contract.source_constraints if item.mode == SourceConstraintMode.ONLY
    ]
    if not only_constraints:
        return False
    meta = metadata or classify_source_authority(url=url)
    for constraint in only_constraints:
        if constraint.scope == "domain" and constraint.values:
            if not _matches_domain_constraint(url, constraint.values):
                return True
        elif constraint.scope == "class" and constraint.values:
            if not _matches_class_constraint(meta, constraint.values):
                return True
        elif constraint.scope == "publisher" and constraint.values:
            publisher = (meta.publisher or "").casefold()
            if not any(value.casefold() in publisher or value.casefold() in _domain(url) for value in constraint.values):
                return True
    return False


def is_source_admissible(
    url: str,
    *,
    contract: ResearchContract | None,
    preferences: list[SourcePreferenceRead] | None = None,
    title: str = "",
) -> tuple[bool, str]:
    if preferences and is_excluded(url, preferences):
        return False, "excluded_by_user_preference"
    metadata = classify_source_authority(url=url, title=title)
    if contract:
        for forbidden in contract.forbidden_source_classes:
            if metadata.source_class == forbidden:
                return False, f"forbidden_source_class:{forbidden.value}"
        if violates_only_constraint(url, contract=contract, metadata=metadata):
            return False, "violates_only_source_constraint"
        if contract.required_source_classes:
            if metadata.source_class not in contract.required_source_classes:
                if metadata.source_class != SourceClass.UNKNOWN:
                    return False, "required_source_class_missing"
    return True, "admissible"


def enrich_search_query_with_policy(query: str, contract: ResearchContract | None) -> str:
    if contract is None:
        return query
    namespaces = official_source_namespaces(contract)
    if not namespaces:
        site_parts: list[str] = []
        for constraint in contract.source_constraints:
            if constraint.mode != SourceConstraintMode.ONLY or constraint.scope != "domain":
                continue
            for domain in constraint.values[:3]:
                site_parts.append(f"site:{domain}")
        if not site_parts:
            return query
        if any(part in query for part in site_parts):
            return query
        return f"{query} ({' OR '.join(site_parts)})"
    if any(f"site:{domain}" in query for domain in namespaces):
        return query
    return f"site:{namespaces[0]} {query}"[:500]


def admission_state_for_source(
    *,
    url: str,
    fetched: bool,
    has_evidence: bool,
    cited_in_report: bool,
    admissible: bool,
) -> SourceAdmissionState:
    if not admissible:
        return SourceAdmissionState.REJECTED
    if cited_in_report:
        return SourceAdmissionState.CITED
    if has_evidence:
        return SourceAdmissionState.EVIDENCE
    if fetched:
        return SourceAdmissionState.ADMISSIBLE
    return SourceAdmissionState.DISCOVERED


def trusted_domain_identities(constraints: list[SourceConstraint]) -> list[str]:
    domains: list[str] = []
    for constraint in constraints:
        if constraint.mode == SourceConstraintMode.ONLY and constraint.scope == "domain":
            domains.extend(constraint.values)
    return domains
