"""First-class connector capability registry.

The registry describes what a connector can legitimately do.  It is data used
by routing and product introspection, not a claim that every public platform is
universally accessible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from deepscout_core.domain.contracts import AuthorityClass, SourceKind


@dataclass(frozen=True, slots=True)
class SourceCapability:
    connector_id: str
    source_kinds: frozenset[SourceKind]
    discovery_supported: bool = False
    fetch_supported: bool = False
    search_supported: bool = False
    authentication_required: bool = False
    structured_data_supported: bool = False
    transcript_supported: bool = False
    freshness: str = "provider_dependent"
    rate_limit: str = "provider_dependent"
    cost: str = "none"
    authority_classes: frozenset[AuthorityClass] = field(default_factory=frozenset)
    content_types: frozenset[str] = field(default_factory=frozenset)
    locale_support: str = "source_dependent"
    query_capabilities: frozenset[str] = field(default_factory=frozenset)
    known_restrictions: tuple[str, ...] = ()


class ConnectorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SourceCapability] = {}

    def register(self, capability: SourceCapability) -> None:
        if capability.connector_id in self._items:
            raise ValueError(f"Duplicate source connector: {capability.connector_id}")
        self._items[capability.connector_id] = capability

    def get(self, connector_id: str) -> SourceCapability | None:
        return self._items.get(connector_id)

    def list(self) -> tuple[SourceCapability, ...]:
        return tuple(self._items.values())

    def discoverers_for(self, kinds: set[SourceKind]) -> tuple[SourceCapability, ...]:
        return tuple(
            item
            for item in self._items.values()
            if item.discovery_supported and (not kinds or bool(item.source_kinds & kinds))
        )


def baseline_connector_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(
        SourceCapability(
            connector_id="indexed_web",
            source_kinds=frozenset(SourceKind),
            discovery_supported=True,
            search_supported=True,
            cost="configured_provider",
            query_capabilities=frozenset(
                {"general", "official", "recent", "independent", "community", "video"}
            ),
            known_restrictions=(
                "Index coverage is provider-dependent",
                "Search snippets are discovery hints, not final evidence",
            ),
        )
    )
    registry.register(
        SourceCapability(
            connector_id="openalex",
            source_kinds=frozenset({SourceKind.ACADEMIC_PAPER, SourceKind.STRUCTURED_API}),
            discovery_supported=True,
            search_supported=True,
            structured_data_supported=True,
            freshness="index_updated",
            rate_limit="public_polite_pool",
            authority_classes=frozenset({AuthorityClass.PRIMARY, AuthorityClass.SECONDARY}),
            content_types=frozenset({"application/json"}),
            query_capabilities=frozenset({"academic", "primary", "data"}),
            known_restrictions=("Metadata/abstract availability varies by work",),
        )
    )
    registry.register(
        SourceCapability(
            connector_id="github_public_api",
            source_kinds=frozenset(
                {
                    SourceKind.REPOSITORY,
                    SourceKind.TECHNICAL_DOCUMENTATION,
                    SourceKind.STRUCTURED_API,
                }
            ),
            discovery_supported=True,
            search_supported=True,
            structured_data_supported=True,
            freshness="live_api",
            rate_limit="GitHub public unauthenticated limit",
            authority_classes=frozenset({AuthorityClass.PRIMARY, AuthorityClass.UNKNOWN}),
            content_types=frozenset({"application/json", "text/markdown"}),
            query_capabilities=frozenset({"code", "repository", "documentation"}),
            known_restrictions=(
                "Public repositories only",
                "Low unauthenticated rate limit; no private repository access",
            ),
        )
    )
    registry.register(
        SourceCapability(
            connector_id="secure_http",
            source_kinds=frozenset(SourceKind),
            fetch_supported=True,
            content_types=frozenset(
                {
                    "text/html",
                    "text/plain",
                    "application/json",
                    "application/xml",
                    "application/rss+xml",
                    "application/atom+xml",
                }
            ),
            known_restrictions=(
                "Public HTTP(S) only",
                "No authentication, CAPTCHA, paywall, or access-control bypass",
            ),
        )
    )
    registry.register(
        SourceCapability(
            connector_id="pdf_document",
            source_kinds=frozenset({SourceKind.DOCUMENT, SourceKind.ACADEMIC_PAPER}),
            fetch_supported=True,
            structured_data_supported=True,
            content_types=frozenset({"application/pdf"}),
            known_restrictions=("Text PDFs only; scanned-image OCR is not bundled",),
        )
    )
    registry.register(
        SourceCapability(
            connector_id="public_video_page",
            source_kinds=frozenset({SourceKind.VIDEO}),
            fetch_supported=True,
            transcript_supported=True,
            content_types=frozenset({"text/html", "application/xml"}),
            known_restrictions=(
                "Only public metadata and captions exposed by the platform",
                "No transcript is claimed when captions are unavailable",
            ),
        )
    )
    return registry
