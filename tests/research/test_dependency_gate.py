"""Tests for hard dependency gating on verified entities."""

from types import SimpleNamespace
from uuid import uuid4

from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_research.contracts.dependency_gate import dependency_satisfied


def _task(key: str, *, depends_on: list[str] | None = None, status=ResearchTaskStatus.PENDING):
    return SimpleNamespace(
        task_key=key,
        depends_on=depends_on or [],
        status=status,
        id=uuid4(),
        priority=1,
        question_id=None,
        objective="",
        allowed_tools=["web_search"],
    )


def test_entity_dependency_requires_verified_entity():
    by_key = {
        "entity-office-holder": _task("entity-office-holder", status=ResearchTaskStatus.COMPLETED),
        "entity-dependent-guidance": _task(
            "entity-dependent-guidance",
            depends_on=["entity-office-holder"],
        ),
    }
    assert not dependency_satisfied(
        dep_key="entity-office-holder",
        by_key=by_key,
        verified={},
    )
    assert dependency_satisfied(
        dep_key="entity-office-holder",
        by_key=by_key,
        verified={"entity-office-holder": {"name": "Example Person"}},
    )
