"""Reconstruct run decisions from the event log. Not a deterministic web replay."""

from __future__ import annotations

from typing import Any


def reconstruct_decisions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map structured events to decision records. Does not re-execute tools."""
    decisions: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        if (
            event_type
            in {
                "workers.allocated",
                "replan.applied",
                "phase.started",
                "phase.completed",
                "run.paused",
                "run.resumed",
                "review.created",
                "review.resolved",
                "run.forked",
                "run.cancelled",
                "run.completed",
            }
            or event_type.startswith("phase.")
            or event_type.endswith("_allocated")
        ):
            decisions.append(
                {
                    "event_type": event_type,
                    "reason": payload.get("reason"),
                    "payload": payload,
                }
            )
    return decisions
