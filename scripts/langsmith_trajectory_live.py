#!/usr/bin/env python3
"""Trajectory evaluation against persisted DeepScout run events (real traces)."""

from __future__ import annotations

import json
import sys
from uuid import UUID

from deepscout_core.settings import get_settings
from deepscout_evaluation.trajectory import (
    REQUIRED_MULTI_AGENT_ACTIONS,
    TrajectoryMatchMode,
    actions_from_run_events,
    match_trajectory,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: langsmith_trajectory_live.py RUN_ID", file=sys.stderr)
        return 1
    run_id = UUID(sys.argv[1])
    settings = get_settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    events = store.list_run_events(run_id)
    payloads = [
        {"event_type": event.event_type, "payload": event.payload or {}} for event in events
    ]
    actions = actions_from_run_events(payloads)
    result = {
        "run_id": str(run_id),
        "actions": actions,
        "exact_required": match_trajectory(
            actions, list(REQUIRED_MULTI_AGENT_ACTIONS), mode=TrajectoryMatchMode.EXACT
        ),
        "unordered_required": match_trajectory(
            actions, list(REQUIRED_MULTI_AGENT_ACTIONS), mode=TrajectoryMatchMode.UNORDERED
        ),
        "subset_noise": match_trajectory(
            list(REQUIRED_MULTI_AGENT_ACTIONS), actions, mode=TrajectoryMatchMode.SUBSET
        ),
        "superset_required": match_trajectory(
            actions, list(REQUIRED_MULTI_AGENT_ACTIONS), mode=TrajectoryMatchMode.SUPERSET
        )
        or match_trajectory(
            [action for action in actions if action.startswith("phase.")],
            ["phase.plan", "phase.research", "phase.report"],
            mode=TrajectoryMatchMode.SUPERSET,
        ),
    }
    print(json.dumps(result))
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
