from uuid import uuid4

from deepscout_research.workers.langgraph_worker import (
    compile_research_worker,
    worker_thread_id,
)


class FakeSearchProvider:
    provider_name = "fake"

    def search(self, query: str, *, max_results: int = 5, timeout_s: float = 15.0):
        from deepscout_core.domain.schemas import SearchResult

        return [
            SearchResult(
                url="https://example.com/battery",
                title="Example",
                snippet="Example battery chemistry overview.",
            )
        ]


def test_worker_graph_prepares_query() -> None:
    from deepscout_research.workers.langgraph_worker import run_worker_graph

    result = run_worker_graph(
        run_id=uuid4(),
        task_id=uuid4(),
        worker_id=uuid4(),
        objective="EV battery chemistries",
        search_provider=FakeSearchProvider(),
    )
    assert result["status"] == "completed"
    assert result.get("result_count", 0) >= 1
    assert "query" in result


def test_worker_graph_checkpoint_resume() -> None:
    run_id = uuid4()
    task_id = uuid4()
    app = compile_research_worker(with_checkpoint=True)
    thread_id = worker_thread_id(run_id=run_id, task_id=task_id)
    config = {
        "configurable": {
            "thread_id": thread_id,
            "search_provider": FakeSearchProvider(),
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
    app.invoke(initial, config=config)
    snapshot = app.get_state(config)
    assert snapshot.values.get("status") in {"searched", "completed", "prepared"}

    resumed = app.invoke(None, config=config)
    assert resumed.get("status") == "completed"
    assert resumed.get("result_count", 0) >= 1
