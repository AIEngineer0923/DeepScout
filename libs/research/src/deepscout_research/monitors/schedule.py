"""Timezone-aware next-run computation. Daily/weekly use wall-clock in the stored timezone."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from deepscout_core.domain.schemas import ResearchMonitorCreate


def resolve_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


def compute_next_run_at(
    spec: ResearchMonitorCreate | object,
    *,
    after: datetime,
) -> datetime:
    tz = resolve_zone(getattr(spec, "timezone", "UTC"))
    kind = getattr(spec, "schedule_kind", "daily")
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    local = after.astimezone(tz)
    if kind == "interval":
        minutes = max(15, int(getattr(spec, "interval_minutes", 1440)))
        return (after + timedelta(minutes=minutes)).astimezone(UTC)
    hour = int(getattr(spec, "hour", 9))
    minute = int(getattr(spec, "minute", 0))
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if kind == "weekly":
        weekday = int(getattr(spec, "weekday", 0))
        days_ahead = (weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate <= local:
            candidate = candidate + timedelta(days=7)
        return candidate.astimezone(UTC)
    if candidate <= local:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(UTC)


def catch_up_next_run(spec: ResearchMonitorCreate | object, *, now: datetime) -> datetime:
    """Skip missed windows; schedule the next future occurrence only (bounded catch-up)."""
    nxt = compute_next_run_at(spec, after=now - timedelta(seconds=1))
    if nxt < now:
        return compute_next_run_at(spec, after=now)
    return nxt
