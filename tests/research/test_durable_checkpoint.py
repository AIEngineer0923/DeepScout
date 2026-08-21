from uuid import uuid4

import pytest
from deepscout_research.workers.checkpointer import reset_worker_checkpointer_cache
from deepscout_research.workers.langgraph_worker import (
    compile_research_worker,
    worker_thread_id,
)


class FakeSearchProvider:
    provider_name = "fake"
    calls = 0

    def search(self, query: str, *, max_results: int = 5, timeout_s: float = 15.0):
        from deepscout_core.domain.schemas import SearchResult

        type(self).calls += 1
        return [
            SearchResult(
                url="https://example.com/battery",
                title="Example",
                snippet="Example battery chemistry overview.",
            )
        ]


@pytest.mark.postgres
def test_postgres_checkpointer_survives_runtime_restart() -> None:
    from tests.db_helpers import database_url, postgres_available

    if not postgres_available():
        pytest.skip("PostgreSQL is not available")

    FakeSearchProvider.calls = 0
    reset_worker_checkpointer_cache()
    url = database_url()
    run_id = uuid4()
    task_id = uuid4()
    search = FakeSearchProvider()
    app = compile_research_worker(
        with_checkpoint=True,
        database_url=url,
        durable_checkpoint=True,
        interrupt_after=["prepare"],
    )
    thread_id = worker_thread_id(run_id=run_id, task_id=task_id)
    config = {
        "configurable": {
            "thread_id": thread_id,
            "search_provider": search,
        }
    }
    initial = {
        "run_id": str(run_id),
        "task_id": str(task_id),
        "worker_id": str(uuid4()),
        "objective": "EV battery chemistries",
        "result_count": 0,
        "search_results": [],
    }
    app.invoke(initial, config=config, durability="sync")
    snapshot = app.get_state(config)
    assert snapshot.values.get("status") == "prepared"

    reset_worker_checkpointer_cache()
    resumed_app = compile_research_worker(
        with_checkpoint=True,
        database_url=url,
        durable_checkpoint=True,
    )
    resumed = resumed_app.invoke(None, config=config, durability="sync")
    assert resumed.get("status") == "completed"
    assert FakeSearchProvider.calls == 1

    other_config = {
        "configurable": {
            "thread_id": worker_thread_id(run_id=uuid4(), task_id=uuid4()),
            "search_provider": search,
        }
    }
    foreign = resumed_app.get_state(other_config)
    assert not foreign.values

    reset_worker_checkpointer_cache()
