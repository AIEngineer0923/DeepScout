from datetime import UTC, datetime
from uuid import uuid4

from deepscout_core.domain.schemas import SourcePreferenceRead
from deepscout_research.source_policy import (
    effective_action,
    is_excluded,
    is_pinned,
    preference_identity,
)


def _pref(action: str, kind: str, value: str) -> SourcePreferenceRead:
    return SourcePreferenceRead(
        id=uuid4(),
        research_run_id=uuid4(),
        action=action,
        identity_kind=kind,
        identity_value=value,
        reason="",
        origin="user",
        created_at=datetime.now(UTC),
    )


def test_url_canonicalization_and_exclude() -> None:
    canonical, host = preference_identity("https://WWW.Example.com/path/")
    assert canonical == "https://example.com/path"
    assert host == "example.com"
    prefs = [_pref("exclude", "url", "https://example.com/path")]
    assert is_excluded("https://www.example.com/path/", prefs)
    assert not is_excluded("https://other.example.org/path", prefs)


def test_domain_exclude_and_pin_do_not_trust() -> None:
    prefs = [
        _pref("exclude", "domain", "blocked.test"),
        _pref("pin", "url", "https://kept.example/a"),
    ]
    assert is_excluded("https://news.blocked.test/article", prefs)
    assert is_pinned("https://kept.example/a", prefs)
    assert not is_pinned("https://other.example/a", prefs)


def test_exclude_wins_over_pin_for_same_identity() -> None:
    prefs = [
        _pref("pin", "url", "https://example.com/a"),
        _pref("exclude", "url", "https://example.com/a"),
    ]
    assert effective_action("https://www.example.com/a", prefs) == "exclude"
    assert is_excluded("https://example.com/a", prefs)
    assert is_pinned("https://example.com/a", prefs)
