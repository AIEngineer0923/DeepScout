"""LangGraph research worker — bounded search loop with checkpointing."""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from deepscout_research.prompts import RESEARCH_WORKER_V1, compose_system_message
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


class WorkerGraphState(TypedDict, total=False):
    run_id: str
    task_id: str
    worker_id: str
    objective: str
    query: str
    result_count: int
    search_results: list[dict[str, Any]]
    status: str
    error: str | None
    system_prompt: str


def _prepare(state: WorkerGraphState) -> WorkerGraphState:
    objective = state.get("objective", "")
    return {
        **state,
        "query": objective[:500],
        "system_prompt": compose_system_message(RESEARCH_WORKER_V1),
        "status": "prepared",
    }


def _search(state: WorkerGraphState, config) -> WorkerGraphState:
    configurable = config.get("configurable", {})
    search_provider = configurable.get("search_provider")
    if search_provider is None:
        return {**state, "status": "failed", "error": "search_provider_missing"}
    query = state.get("query", "")
    try:
        results = search_provider.search(query, max_results=3)
        serialized = [
            {"url": item.url, "title": item.title, "snippet": item.snippet, "score": item.score}
            for item in results
        ]
        return {
            **state,
            "search_results": serialized,
            "result_count": len(serialized),
            "status": "searched",
            "error": None,
        }
    except Exception as exc:
        return {**state, "status": "failed", "error": str(exc)[:500]}


def _finalize(state: WorkerGraphState) -> WorkerGraphState:
    if state.get("status") == "failed":
        return state
    return {**state, "status": "completed"}


def build_research_worker_graph() -> StateGraph:
    graph = StateGraph(WorkerGraphState)
    graph.add_node("prepare", _prepare)
    graph.add_node("search", _search)
    graph.add_node("finalize", _finalize)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "search")
    graph.add_edge("search", "finalize")
    graph.add_edge("finalize", END)
    return graph


_CHECKPOINTER = MemorySaver()


def compile_research_worker(*, with_checkpoint: bool = True):
    graph = build_research_worker_graph()
    if with_checkpoint:
        return graph.compile(checkpointer=_CHECKPOINTER)
    return graph.compile()


def worker_thread_id(*, run_id: UUID, task_id: UUID) -> str:
    return f"{run_id}:{task_id}"


def run_worker_graph(
    *,
    run_id: UUID,
    task_id: UUID,
    worker_id: UUID,
    objective: str,
    search_provider,
    resume: bool = False,
) -> WorkerGraphState:
    app = compile_research_worker(with_checkpoint=True)
    thread_id = worker_thread_id(run_id=run_id, task_id=task_id)
    config = {
        "configurable": {
            "thread_id": thread_id,
            "search_provider": search_provider,
        }
    }
    initial: WorkerGraphState = {
        "run_id": str(run_id),
        "task_id": str(task_id),
        "worker_id": str(worker_id),
        "objective": objective,
        "result_count": 0,
        "search_results": [],
    }
    if resume:
        snapshot = app.get_state(config)
        if snapshot.values:
            return app.invoke(None, config=config)
    return app.invoke(initial, config=config)
