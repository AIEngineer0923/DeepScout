"""Research run preferences — geographic focus, freshness, model policy, exclusions."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

GeographicFocusMode = Literal["automatic", "global", "regions"]
FreshnessMode = Literal["automatic", "explicit"]
FreshnessPolicy = Literal["any", "24h", "7d", "30d", "1y"]
ModelPolicyMode = Literal["automatic", "quality", "balanced", "speed", "cost", "manual"]


class GeographicFocus(BaseModel):
    mode: GeographicFocusMode = "automatic"
    regions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("regions")
    @classmethod
    def normalize_regions(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in value:
            item = raw.strip()
            if not item:
                continue
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out


class SourceFreshness(BaseModel):
    mode: FreshnessMode = "automatic"
    policy: FreshnessPolicy = "any"


class ModelPolicy(BaseModel):
    mode: ModelPolicyMode = "automatic"
    provider: str | None = Field(default=None, max_length=32)
    model: str | None = Field(default=None, max_length=128)


class ResearchPreferences(BaseModel):
    geographic_focus: GeographicFocus = Field(default_factory=GeographicFocus)
    freshness: SourceFreshness = Field(default_factory=SourceFreshness)
    model_policy: ModelPolicy = Field(default_factory=ModelPolicy)
    excluded_domains: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("excluded_domains")
    @classmethod
    def normalize_domains(cls, value: list[str]) -> list[str]:
        return normalize_excluded_domains(value)


def normalize_excluded_domains(domains: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in domains:
        domain = normalize_domain(raw)
        if domain and domain not in seen:
            seen.add(domain)
            out.append(domain)
    return out


def normalize_domain(raw: str) -> str | None:
    text = raw.strip().lower()
    if not text:
        return None
    if "://" in text:
        host = urlparse(text).netloc
    else:
        host = text.split("/")[0]
    host = host.removeprefix("www.")
    if not host or "." not in host:
        return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z]{2,}", host):
        return None
    return host


_GEO_HINTS: tuple[tuple[str, str], ...] = (
    ("italia", "Italy"),
    ("italy", "Italy"),
    ("italian", "Italy"),
    ("stati uniti", "United States"),
    ("united states", "United States"),
    ("u.s.", "United States"),
    ("usa", "United States"),
    ("america", "United States"),
    ("france", "France"),
    ("francia", "France"),
    ("germany", "Germany"),
    ("germania", "Germany"),
    ("spain", "Spain"),
    ("spagna", "Spain"),
    ("uk", "United Kingdom"),
    ("united kingdom", "United Kingdom"),
    ("regno unito", "United Kingdom"),
    ("europe", "Europe"),
    ("europa", "Europe"),
    ("global", "Global"),
    ("mondiale", "Global"),
)

_RECENT_HINTS = (
    "latest",
    "recent",
    "ultime",
    "ultimi",
    "ultima",
    "novità",
    "news",
    "oggi",
    "today",
    "2026",
    "2025",
)


def infer_geographic_regions(goal: str) -> list[str]:
    lowered = goal.casefold()
    found: list[str] = []
    for hint, region in _GEO_HINTS:
        if hint in lowered and region not in found:
            found.append(region)
    return found


def infer_freshness_policy(goal: str) -> FreshnessPolicy:
    lowered = goal.casefold()
    if any(hint in lowered for hint in _RECENT_HINTS):
        return "30d"
    if any(word in lowered for word in ("history", "historical", "storia", "origins", "evolution")):
        return "any"
    return "any"


class ResolvedResearchPreferences(BaseModel):
    geographic_focus_mode: GeographicFocusMode
    geographic_regions: list[str]
    freshness_mode: FreshnessMode
    freshness_policy: FreshnessPolicy
    fresher_than: datetime | None = None
    model_policy_mode: ModelPolicyMode
    model_provider: str | None = None
    model_name: str | None = None
    excluded_domains: list[str] = Field(default_factory=list)


def resolve_preferences(
    preferences: ResearchPreferences, *, goal: str
) -> ResolvedResearchPreferences:
    geo_mode = preferences.geographic_focus.mode
    regions = list(preferences.geographic_focus.regions)
    if geo_mode == "automatic":
        inferred = infer_geographic_regions(goal)
        if inferred:
            geo_mode = "regions"
            regions = inferred
        else:
            geo_mode = "global"
            regions = []

    fresh_mode = preferences.freshness.mode
    policy = preferences.freshness.policy
    if fresh_mode == "automatic":
        policy = infer_freshness_policy(goal)

    fresher_than = freshness_cutoff(policy)

    return ResolvedResearchPreferences(
        geographic_focus_mode=geo_mode,
        geographic_regions=regions,
        freshness_mode=fresh_mode,
        freshness_policy=policy,
        fresher_than=fresher_than,
        model_policy_mode=preferences.model_policy.mode,
        model_provider=preferences.model_policy.provider,
        model_name=preferences.model_policy.model,
        excluded_domains=list(preferences.excluded_domains),
    )


def freshness_cutoff(policy: FreshnessPolicy) -> datetime | None:
    now = datetime.now(UTC)
    if policy == "any":
        return None
    if policy == "24h":
        return now - timedelta(hours=24)
    if policy == "7d":
        return now - timedelta(days=7)
    if policy == "30d":
        return now - timedelta(days=30)
    if policy == "1y":
        return now - timedelta(days=365)
    return None


def enrich_search_query(query: str, resolved: ResolvedResearchPreferences) -> str:
    if resolved.geographic_focus_mode != "regions" or not resolved.geographic_regions:
        return query
    region_hint = ", ".join(resolved.geographic_regions[:3])
    if region_hint.casefold() in query.casefold():
        return query
    return f"{query} ({region_hint})"


def search_provider_options(resolved: ResolvedResearchPreferences) -> dict[str, object]:
    opts: dict[str, object] = {}
    if resolved.freshness_policy in {"24h", "7d", "30d"}:
        days = {"24h": 1, "7d": 7, "30d": 30}[resolved.freshness_policy]
        opts["days"] = days
        opts["topic"] = "news"
    elif resolved.freshness_policy == "1y":
        opts["days"] = 365
    return opts
