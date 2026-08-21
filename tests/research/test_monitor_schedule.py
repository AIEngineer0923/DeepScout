from datetime import UTC, datetime

from deepscout_core.domain.schemas import ResearchMonitorCreate
from deepscout_research.monitors.schedule import catch_up_next_run, compute_next_run_at


def test_daily_uses_named_timezone_not_utc() -> None:
    spec = ResearchMonitorCreate(
        name="m",
        goal="g",
        schedule_kind="daily",
        timezone="Europe/Rome",
        hour=9,
        minute=0,
    )
    after = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
    nxt = compute_next_run_at(spec, after=after)
    assert nxt.tzinfo is not None
    local = nxt.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Rome"))
    assert local.hour == 9


def test_dst_fall_back_rome() -> None:
    spec = ResearchMonitorCreate(
        name="m",
        goal="g",
        schedule_kind="daily",
        timezone="Europe/Rome",
        hour=9,
        minute=0,
    )
    before = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    nxt = compute_next_run_at(spec, after=before)
    local = nxt.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Rome"))
    assert local.hour == 9
    assert local.day == 25


def test_dst_spring_forward_rome() -> None:
    spec = ResearchMonitorCreate(
        name="m",
        goal="g",
        schedule_kind="daily",
        timezone="Europe/Rome",
        hour=9,
        minute=0,
    )
    before = datetime(2026, 3, 28, 22, 0, tzinfo=UTC)
    nxt = compute_next_run_at(spec, after=before)
    local = nxt.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Rome"))
    assert local.hour == 9
    assert local.day == 29


def test_bounded_catch_up_skips_missed_windows() -> None:
    spec = ResearchMonitorCreate(
        name="m",
        goal="g",
        schedule_kind="interval",
        interval_minutes=60,
        timezone="UTC",
    )
    now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    nxt = catch_up_next_run(spec, now=now)
    assert nxt >= now
