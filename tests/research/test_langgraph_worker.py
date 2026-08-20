"""LangGraph worker graph tests."""

from uuid import uuid4

from deepscout_research.workers.langgraph_worker import run_worker_graph


def test_worker_graph_prepares_query() -> None:
    result = run_worker_graph(task_id=uuid4(), objective="EV battery chemistries")
    assert result["status"] == "completed"
    assert "query" in result
