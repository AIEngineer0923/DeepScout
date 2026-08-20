"""LangGraph research worker subgraph — bounded local agent loop."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph


class WorkerState(TypedDict, total=False):
    task_id: str
    objective: str
    query: str
    result_count: int
    status: str


def build_research_worker_graph() -> StateGraph:
    """Minimal worker graph exercised in tests and runtime traces."""

    def prepare(state: WorkerState) -> WorkerState:
        objective = state.get("objective", "")
        return {
            **state,
            "query": objective[:500],
            "status": "prepared",
        }

    def finalize(state: WorkerState) -> WorkerState:
        return {**state, "status": "completed"}

    graph = StateGraph(WorkerState)
    graph.add_node("prepare", prepare)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "finalize")
    graph.add_edge("finalize", END)
    return graph


def compile_research_worker():
    return build_research_worker_graph().compile()


def run_worker_graph(*, task_id: UUID, objective: str) -> WorkerState:
    app = compile_research_worker()
    return app.invoke(
        {
            "task_id": str(task_id),
            "objective": objective,
            "result_count": 0,
        }
    )
