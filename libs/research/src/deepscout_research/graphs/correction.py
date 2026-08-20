"""Bounded LangGraph correction loop: validate → critic (if needed) → done."""

from __future__ import annotations

from typing import TypedDict

from deepscout_core.domain.schemas import CriticResult
from langgraph.graph import END, START, StateGraph


class CorrectionState(TypedDict, total=False):
    artifact_type: str
    passed: bool
    issues: list[str]
    rounds: int
    max_rounds: int
    critic_invoked: bool
    status: str


def _deterministic_validate(state: CorrectionState) -> CorrectionState:
    issues = list(state.get("issues") or [])
    passed = state.get("passed", True) and not issues
    return {**state, "passed": passed, "status": "validated"}


def _should_invoke_critic(state: CorrectionState) -> str:
    if state.get("passed"):
        return "done"
    if state.get("rounds", 0) >= state.get("max_rounds", 1):
        return "done"
    return "critic"


def _run_critic(state: CorrectionState) -> CorrectionState:
    issues = list(state.get("issues") or ["validation_failed"])
    result = CriticResult(
        passed=False,
        artifact_type=state.get("artifact_type", "artifact"),
        severity="fail",
        issues=issues[:10],
    )
    return {
        **state,
        "critic_invoked": True,
        "issues": result.issues,
        "passed": result.passed,
        "rounds": state.get("rounds", 0) + 1,
        "status": "critic_completed",
    }


def _finalize(state: CorrectionState) -> CorrectionState:
    status = "passed" if state.get("passed") else "failed"
    return {**state, "status": status}


def build_correction_graph() -> StateGraph:
    graph = StateGraph(CorrectionState)
    graph.add_node("validate", _deterministic_validate)
    graph.add_node("critic", _run_critic)
    graph.add_node("finalize", _finalize)
    graph.add_edge(START, "validate")
    graph.add_conditional_edges(
        "validate",
        _should_invoke_critic,
        {"critic": "critic", "done": "finalize"},
    )
    graph.add_edge("critic", "finalize")
    graph.add_edge("finalize", END)
    return graph


def run_correction_loop(
    *,
    artifact_type: str,
    passed: bool,
    issues: list[str] | None = None,
    max_rounds: int = 1,
) -> CorrectionState:
    app = build_correction_graph().compile()
    initial: CorrectionState = {
        "artifact_type": artifact_type,
        "passed": passed,
        "issues": issues or [],
        "rounds": 0,
        "max_rounds": max_rounds,
        "critic_invoked": False,
    }
    return app.invoke(initial)
