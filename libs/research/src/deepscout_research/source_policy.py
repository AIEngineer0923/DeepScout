"""PIN / EXCLUDE source constraints. Application-owned; retrieved text cannot mutate these."""

from __future__ import annotations

from urllib.parse import urlparse

from deepscout_core.domain.schemas import SourcePreferenceRead

from deepscout_research.fetch.url_normalize import normalize_source_url


def preference_identity(url: str) -> tuple[str, str]:
    canonical = normalize_source_url(url)
    host = urlparse(canonical).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return canonical, host.lower()


def is_excluded(url: str, preferences: list[SourcePreferenceRead]) -> bool:
    canonical, host = preference_identity(url)
    for item in preferences:
        if item.action != "exclude":
            continue
        if item.identity_kind == "url" and normalize_source_url(item.identity_value) == canonical:
            return True
        if item.identity_kind == "domain" and host == item.identity_value.lower().lstrip("."):
            return True
        suffix = "." + item.identity_value.lower().lstrip(".")
        if item.identity_kind == "domain" and host.endswith(suffix):
            return True
    return False


def is_pinned(url: str, preferences: list[SourcePreferenceRead]) -> bool:
    canonical, host = preference_identity(url)
    for item in preferences:
        if item.action != "pin":
            continue
        if item.identity_kind == "url" and normalize_source_url(item.identity_value) == canonical:
            return True
        if item.identity_kind == "domain" and (
            host == item.identity_value.lower().lstrip(".")
            or host.endswith("." + item.identity_value.lower().lstrip("."))
        ):
            return True
    return False


def effective_action(url: str, preferences: list[SourcePreferenceRead]) -> str:
    """EXCLUDE always wins over PIN for the same identity."""
    if is_excluded(url, preferences):
        return "exclude"
    if is_pinned(url, preferences):
        return "pin"
    return "normal"


def filter_search_urls(urls: list[str], preferences: list[SourcePreferenceRead]) -> list[str]:
    return [url for url in urls if not is_excluded(url, preferences)]


def pinned_identities(preferences: list[SourcePreferenceRead]) -> list[str]:
    return [item.identity_value for item in preferences if item.action == "pin"]
