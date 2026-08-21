"""Tests for research preference resolution and normalization."""

from deepscout_core.domain.research_preferences import (
    GeographicFocus,
    ResearchPreferences,
    SourceFreshness,
    enrich_search_query,
    infer_geographic_regions,
    normalize_domain,
    resolve_preferences,
    search_provider_options,
)


def test_normalize_domain_strips_www() -> None:
    assert normalize_domain("https://www.example.com/path") == "example.com"
    assert normalize_domain("spam.test") == "spam.test"


def test_infer_italy_from_goal() -> None:
    regions = infer_geographic_regions("Obblighi di fatturazione elettronica in Italia nel 2026")
    assert "Italy" in regions


def test_automatic_geo_resolves_from_goal() -> None:
    prefs = ResearchPreferences(geographic_focus=GeographicFocus(mode="automatic"))
    resolved = resolve_preferences(prefs, goal="Normativa italiana sulla privacy")
    assert resolved.geographic_focus_mode == "regions"
    assert "Italy" in resolved.geographic_regions


def test_explicit_geo_regions() -> None:
    prefs = ResearchPreferences(
        geographic_focus=GeographicFocus(mode="regions", regions=["United States"])
    )
    resolved = resolve_preferences(prefs, goal="SaaS market analysis")
    assert resolved.geographic_regions == ["United States"]


def test_enrich_search_query_adds_region() -> None:
    prefs = ResearchPreferences(geographic_focus=GeographicFocus(mode="regions", regions=["Italy"]))
    resolved = resolve_preferences(prefs, goal="billing rules")
    enriched = enrich_search_query("electronic invoicing requirements", resolved)
    assert "Italy" in enriched


def test_freshness_recent_goal() -> None:
    prefs = ResearchPreferences(freshness=SourceFreshness(mode="automatic"))
    resolved = resolve_preferences(prefs, goal="Ultime novità su GDPR enforcement")
    assert resolved.freshness_policy == "30d"
    assert search_provider_options(resolved).get("days") == 30


def test_excluded_domains_normalized() -> None:
    prefs = ResearchPreferences(excluded_domains=["WWW.Spam.COM", "spam.com", "invalid"])
    assert prefs.excluded_domains == ["spam.com"]
