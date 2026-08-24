"""Maintained, legitimate structured discovery adapters with no access bypass."""

from __future__ import annotations

import base64
import re
from typing import Protocol

import httpx
from deepscout_core.domain.contracts import SourceKind
from deepscout_core.domain.schemas import SearchResult

from deepscout_research.source_fabric.registry import SourceCapability
from deepscout_research.source_fabric.strategy import DiscoveryRequest, evidence_role_for_kind

_USER_AGENT = "DeepScout/0.1.1 (+https://github.com/francescoveryra-dot/deepscout)"
_MAX_API_RESPONSE_BYTES = 2 * 1024 * 1024
_GITHUB_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class DiscoveryProvider(Protocol):
    provider_name: str
    capability: SourceCapability

    def discover(self, request: DiscoveryRequest) -> list[SearchResult]: ...

    def close(self) -> None: ...


def _abstract_from_inverted_index(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    positioned: list[tuple[int, str]] = []
    for token, positions in value.items():
        if not isinstance(token, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned.append((position, token))
    return " ".join(token for _, token in sorted(positioned))[:40_000]


def _bounded_json(response: httpx.Response) -> dict[str, object]:
    """Reject unexpectedly large structured responses before parsing them."""

    declared_size = response.headers.get("content-length")
    if declared_size:
        try:
            if int(declared_size) > _MAX_API_RESPONSE_BYTES:
                raise ValueError("structured discovery response exceeds size limit")
        except ValueError as exc:
            if "exceeds size limit" in str(exc):
                raise
    if len(response.content) > _MAX_API_RESPONSE_BYTES:
        raise ValueError("structured discovery response exceeds size limit")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("structured discovery response must be a JSON object")
    return payload


class OpenAlexDiscoveryProvider:
    provider_name = "openalex"

    def __init__(self, capability: SourceCapability) -> None:
        self.capability = capability
        self._client = httpx.Client(
            base_url="https://api.openalex.org",
            timeout=15.0,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )

    def discover(self, request: DiscoveryRequest) -> list[SearchResult]:
        response = self._client.get(
            "/works",
            params={
                "search": request.query[:300],
                "per-page": min(10, max(1, request.max_results)),
                "select": (
                    "id,doi,title,publication_date,authorships,primary_location,"
                    "abstract_inverted_index,cited_by_count,type"
                ),
            },
        )
        response.raise_for_status()
        payload = _bounded_json(response)
        output: list[SearchResult] = []
        for item in payload.get("results", [])[: request.max_results]:
            title = str(item.get("title") or "")
            abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
            authors = []
            for authorship in item.get("authorships") or []:
                author = (authorship or {}).get("author") or {}
                if author.get("display_name"):
                    authors.append(str(author["display_name"]))
            location = item.get("primary_location") or {}
            source = location.get("source") or {}
            landing = str(location.get("landing_page_url") or "")
            canonical = str(item.get("doi") or landing or item.get("id") or "")
            if not canonical:
                continue
            structured = "\n".join(
                part
                for part in (
                    title,
                    f"Authors: {', '.join(authors[:20])}" if authors else "",
                    f"Publication date: {item.get('publication_date')}"
                    if item.get("publication_date")
                    else "",
                    f"Type: {item.get('type')}" if item.get("type") else "",
                    f"DOI: {item.get('doi')}" if item.get("doi") else "",
                    abstract,
                )
                if part
            )
            cited = int(item.get("cited_by_count") or 0)
            output.append(
                SearchResult(
                    url=canonical,
                    fetch_url=str(item.get("id") or ""),
                    title=title,
                    snippet=abstract[:8000],
                    score=min(1.0, 0.45 + cited / 1000),
                    discovery_provider=self.provider_name,
                    source_kind=SourceKind.ACADEMIC_PAPER.value,
                    publisher=str(source.get("display_name") or ""),
                    published_at=str(item.get("publication_date") or ""),
                    query_strategy=request.strategy.value,
                    evidence_role=evidence_role_for_kind(SourceKind.ACADEMIC_PAPER),
                    structured_content=structured,
                    structured_mime_type="text/plain",
                    provenance={
                        "connector": self.provider_name,
                        "api_record": str(item.get("id") or ""),
                        "original_url": canonical,
                        "content_scope": "metadata_and_abstract",
                    },
                )
            )
        return output

    def close(self) -> None:
        self._client.close()


class GitHubDiscoveryProvider:
    provider_name = "github_public_api"

    def __init__(self, capability: SourceCapability) -> None:
        self.capability = capability
        self._client = httpx.Client(
            base_url="https://api.github.com",
            timeout=15.0,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    @staticmethod
    def _clean_query(query: str) -> str:
        tokens = re.findall(r"[A-Za-z0-9_.+-]+", query)
        return " ".join(tokens[:20])[:240]

    def _readme(self, full_name: str) -> tuple[str, str]:
        if not _GITHUB_REPOSITORY_RE.fullmatch(full_name):
            return "", ""
        response = self._client.get(f"/repos/{full_name}/readme")
        if response.status_code != 200:
            return "", ""
        payload = _bounded_json(response)
        encoded = str(payload.get("content") or "").replace("\n", "")
        if not encoded:
            return "", ""
        try:
            text = base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")
        except (ValueError, UnicodeError):
            return "", ""
        return text[:100_000], str(payload.get("html_url") or "")

    def discover(self, request: DiscoveryRequest) -> list[SearchResult]:
        response = self._client.get(
            "/search/repositories",
            params={
                "q": f"{self._clean_query(request.query)} in:name,description,readme",
                "per_page": min(5, max(1, request.max_results)),
            },
        )
        response.raise_for_status()
        output: list[SearchResult] = []
        payload = _bounded_json(response)
        for item in payload.get("items", [])[: request.max_results]:
            full_name = str(item.get("full_name") or "")
            canonical = str(item.get("html_url") or "")
            if not full_name or not canonical:
                continue
            readme, readme_url = self._readme(full_name)
            description = str(item.get("description") or "")
            structured = "\n".join(
                part
                for part in (
                    f"Repository: {full_name}",
                    description,
                    f"Default branch: {item.get('default_branch')}",
                    f"Language: {item.get('language')}",
                    f"Latest push: {item.get('pushed_at')}",
                    readme,
                )
                if part and part != "None"
            )
            stars = int(item.get("stargazers_count") or 0)
            output.append(
                SearchResult(
                    url=readme_url or canonical,
                    fetch_url=str(item.get("url") or ""),
                    title=full_name,
                    snippet=description[:8000],
                    score=min(1.0, 0.4 + stars / 100_000),
                    discovery_provider=self.provider_name,
                    source_kind=(
                        SourceKind.TECHNICAL_DOCUMENTATION.value
                        if readme
                        else SourceKind.REPOSITORY.value
                    ),
                    publisher=str((item.get("owner") or {}).get("login") or ""),
                    published_at=str(item.get("pushed_at") or ""),
                    query_strategy=request.strategy.value,
                    evidence_role=evidence_role_for_kind(
                        SourceKind.TECHNICAL_DOCUMENTATION if readme else SourceKind.REPOSITORY
                    ),
                    structured_content=structured,
                    structured_mime_type="text/markdown" if readme else "application/json",
                    provenance={
                        "connector": self.provider_name,
                        "api_record": str(item.get("url") or ""),
                        "original_url": readme_url or canonical,
                        "repository": full_name,
                    },
                )
            )
        return output

    def close(self) -> None:
        self._client.close()
