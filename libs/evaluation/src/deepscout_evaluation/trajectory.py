"""Trajectory match evaluators for DeepScout phase/tool sequences.

Parallel workers may complete in any order. Use unordered/superset/subset
semantics rather than exact linear order unless order is required.
"""

from __future__ import annotations

from enum import StrEnum


class TrajectoryMatchMode(StrEnum):
    EXACT = "exact"
    UNORDERED = "unordered"
    SUBSET = "subset"
    SUPERSET = "superset"


def match_trajectory(
    actual: list[str],
    reference: list[str],
    *,
    mode: TrajectoryMatchMode,
) -> bool:
    if mode == TrajectoryMatchMode.EXACT:
        return actual == reference
    actual_set = set(actual)
    reference_set = set(reference)
    if mode == TrajectoryMatchMode.UNORDERED:
        return actual_set == reference_set
    if mode == TrajectoryMatchMode.SUBSET:
        return actual_set <= reference_set
    if mode == TrajectoryMatchMode.SUPERSET:
        return actual_set >= reference_set
    return False


REQUIRED_MULTI_AGENT_ACTIONS = (
    "phase.plan",
    "phase.research",
    "tool.web_search",
    "phase.fetch",
    "phase.extract",
    "phase.verify",
    "phase.critic",
    "phase.report",
)


def actions_from_run_events(events: list[dict]) -> list[str]:
    actions: list[str] = []
    for event in events:
        event_type = str(event.get("event_type") or event.get("type") or "")
        payload = event.get("payload") or {}
        phase = payload.get("phase")
        if event_type == "phase.started" and phase:
            actions.append(f"phase.{phase}")
        elif event_type.startswith("phase."):
            continue
        elif event_type:
            actions.append(event_type)
    tool_calls = payload_tool_actions(events)
    return actions + tool_calls


def payload_tool_actions(events: list[dict]) -> list[str]:
    actions: list[str] = []
    for event in events:
        payload = event.get("payload") or {}
        if payload.get("workers") or payload.get("ready_tasks"):
            actions.append("tool.web_search")
            break
    return actions
