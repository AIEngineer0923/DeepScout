from datetime import UTC, datetime

import pytest
from deepscout_core.domain.enums import RunLineageKind
from deepscout_core.domain.schemas import (
    ResearchMonitorCreate,
    ResearchRunCreate,
    SourcePreferenceWrite,
)
from deepscout_research.followup import select_followup_context
from deepscout_research.run_diff import compare_runs

pytestmark = pytest.mark.postgres


def test_followup_context_is_bounded(store, settings) -> None:
    parent = store.create_run(ResearchRunCreate(goal="parent goal"), settings)
    ctx = select_followup_context(store, parent.id, "verify the battery claim")
    assert ctx["role"] == "untrusted_historical_DATA"
    assert "SourceSnapshot" in ctx["authority"]
    assert len(str(ctx)) < 8000


def test_source_preference_roundtrip(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="prefs"), settings)
    store.upsert_source_preference(
        run.id,
        SourcePreferenceWrite(action="exclude", identity_kind="domain", identity_value="spam.test"),
    )
    child = store.create_run(
        ResearchRunCreate(goal="child"),
        settings,
        parent_run_id=run.id,
        lineage_kind=RunLineageKind.FOLLOWUP.value,
        fork_reason="followup",
    )
    store.copy_source_preferences(run.id, child.id)
    copied = store.list_source_preferences(child.id)
    assert copied[0].action == "exclude"
    assert copied[0].origin == "inherited"


def test_run_diff_rejects_same_run(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="diff me"), settings)
    with pytest.raises(ValueError):
        compare_runs(store, run.id, run.id)


def test_monitor_lease_is_exclusive(store) -> None:
    now = datetime.now(UTC)
    payload = ResearchMonitorCreate(name="lease", goal="goal", timezone="UTC")
    row = store.create_monitor(payload, next_run_at=now)
    first = store.claim_due_monitors("owner-a", now=now, lease_seconds=60)
    second = store.claim_due_monitors("owner-b", now=now, lease_seconds=60)
    assert [item.id for item in first] == [row.id]
    assert second == []


def test_listen_notify_wakes_before_poll(postgres_ready) -> None:
    import os
    import threading
    import time
    import uuid

    from deepscout_persistence.session import get_engine
    from deepscout_research.streaming.notify import NotifyWaiter
    from sqlalchemy import text
    from tests.db_helpers import database_url

    run_id = uuid.uuid4()
    waiter = NotifyWaiter(database_url())
    woke = {"value": False, "ms": None}

    def listen() -> None:
        started = time.perf_counter()
        woke["value"] = waiter.wait(run_id, 1.5)
        woke["ms"] = (time.perf_counter() - started) * 1000

    thread = threading.Thread(target=listen)
    thread.start()
    time.sleep(0.15)
    engine = get_engine(database_url())
    with engine.connect() as conn:
        autocommit = conn.execution_options(isolation_level="AUTOCOMMIT")
        autocommit.execute(text("SELECT pg_notify('deepscout_run_events', :p)"), {"p": str(run_id)})
    thread.join(timeout=3)
    waiter.close()
    assert woke["value"] is True
    assert woke["ms"] is not None and woke["ms"] < 800
    os.environ.setdefault("DEEPSCOUT_LISTEN_WOKE", "1")
