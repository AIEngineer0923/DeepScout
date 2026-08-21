"""Load resolved research preferences from a run config snapshot."""

from __future__ import annotations

from deepscout_core.domain.research_preferences import (
    ResearchPreferences,
    ResolvedResearchPreferences,
    resolve_preferences,
)


def preferences_from_snapshot(snapshot: dict | None, *, goal: str) -> ResolvedResearchPreferences:
    raw = (snapshot or {}).get("research_preferences")
    if isinstance(raw, dict):
        prefs = ResearchPreferences.model_validate(raw)
    else:
        prefs = ResearchPreferences()
    return resolve_preferences(prefs, goal=goal)


def snapshot_with_preferences(
    snapshot: dict, preferences: ResearchPreferences, *, goal: str
) -> dict:
    resolved = resolve_preferences(preferences, goal=goal)
    merged = dict(snapshot)
    merged["research_preferences"] = preferences.model_dump(mode="json")
    merged["research_preferences_resolved"] = {
        "geographic_focus_mode": resolved.geographic_focus_mode,
        "geographic_regions": resolved.geographic_regions,
        "freshness_mode": resolved.freshness_mode,
        "freshness_policy": resolved.freshness_policy,
        "fresher_than": resolved.fresher_than.isoformat() if resolved.fresher_than else None,
        "model_policy_mode": resolved.model_policy_mode,
        "model_provider": resolved.model_provider,
        "model_name": resolved.model_name,
        "excluded_domains": resolved.excluded_domains,
    }
    return merged
