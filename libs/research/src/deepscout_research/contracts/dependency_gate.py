"""Hard dependency gating using verified application state."""

from __future__ import annotations

import uuid

from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import ResearchTaskRead
from deepscout_persistence.store import ResearchStore

from deepscout_research.tasks.graph import TaskGraph

_ENTITY_TASK_KEYS = frozenset({"entity-office-holder"})


def verified_entities(snapshot: dict | None) -> dict[str, dict]:
    if not snapshot:
        return {}
    raw = snapshot.get("verified_entities") or {}
    return raw if isinstance(raw, dict) else {}


def dependency_satisfied(
    *,
    dep_key: str,
    by_key: dict[str, ResearchTaskRead],
    verified: dict[str, dict],
) -> bool:
    if dep_key in _ENTITY_TASK_KEYS:
        return bool(verified.get(dep_key))
    dep_task = by_key.get(dep_key)
    if dep_task is None:
        return False
    return dep_task.status == ResearchTaskStatus.COMPLETED


def ready_tasks_with_verified_deps(
    store: ResearchStore,
    run_id: uuid.UUID,
    tasks: list[ResearchTaskRead],
) -> list[ResearchTaskRead]:
    graph = TaskGraph(tuple(tasks))
    graph.validate_dependencies()
    row = store.get_run_row(run_id)
    verified = verified_entities(row.config_snapshot if row else None)
    by_key = graph.by_key()
    ready: list[ResearchTaskRead] = []
    for task in graph.ready_tasks():
        if all(dependency_satisfied(dep_key=dep, by_key=by_key, verified=verified) for dep in task.depends_on):
            ready.append(task)
    return ready
