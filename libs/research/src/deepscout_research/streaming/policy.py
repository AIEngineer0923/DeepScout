"""Streaming policy for DeepScout agent runtime.

PostgreSQL run events remain authoritative. The browser stream is a
projection, never a second source of truth. Disconnect does not cancel a run.
"""

from __future__ import annotations

from enum import StrEnum

from deepscout_core.domain.enums import AgentRole
from deepscout_core.domain.events import ResearchEventType


class StreamLayer(StrEnum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    SUBAGENT = "subagent"
    TOOL = "tool"
    LLM_TOKEN = "llm_token"


# Lifecycle events must be replayed after reconnect. Progress-only events may
# be coalesced in the UI but are still persisted when emitted.
AUTHORITATIVE_EVENT_TYPES = frozenset(
    {
        ResearchEventType.RUN_STARTED,
        ResearchEventType.RUN_COMPLETED,
        ResearchEventType.RUN_FAILED,
        ResearchEventType.RUN_CANCELLED,
        ResearchEventType.RUN_PAUSED,
        ResearchEventType.REVIEW_REQUESTED,
        ResearchEventType.REVIEW_RESOLVED,
        ResearchEventType.REPLAN_APPLIED,
        ResearchEventType.REPORT_READY,
        ResearchEventType.RUN_FORKED,
        ResearchEventType.WORKERS_ALLOCATED,
        ResearchEventType.SKILL_SELECTED,
        ResearchEventType.EVIDENCE_CREATED,
        ResearchEventType.CONTRADICTION_DETECTED,
    }
)

COALESCABLE_EVENT_TYPES = frozenset(
    {
        ResearchEventType.WORKER_PROGRESS,
        ResearchEventType.BUDGET_UPDATED,
        ResearchEventType.PHASE_STARTED,
    }
)

EVENT_LAYER: dict[ResearchEventType, StreamLayer] = {
    ResearchEventType.RUN_STARTED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.RUN_COMPLETED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.RUN_FAILED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.RUN_CANCELLED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.RUN_PAUSED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.PHASE_STARTED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.PHASE_COMPLETED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.TASK_READY: StreamLayer.ORCHESTRATOR,
    ResearchEventType.WORKERS_ALLOCATED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.REPLAN_APPLIED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.REVIEW_REQUESTED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.REVIEW_RESOLVED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.RUN_FORKED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.REPORT_READY: StreamLayer.ORCHESTRATOR,
    ResearchEventType.CRITIC_STARTED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.CRITIC_COMPLETED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.WORKER_STARTED: StreamLayer.WORKER,
    ResearchEventType.WORKER_PROGRESS: StreamLayer.WORKER,
    ResearchEventType.WORKER_COMPLETED: StreamLayer.WORKER,
    ResearchEventType.WORKER_FAILED: StreamLayer.WORKER,
    ResearchEventType.SKILL_SELECTED: StreamLayer.WORKER,
    ResearchEventType.SOURCE_DISCOVERED: StreamLayer.TOOL,
    ResearchEventType.SOURCE_FETCHED: StreamLayer.TOOL,
    ResearchEventType.CLAIM_CREATED: StreamLayer.TOOL,
    ResearchEventType.EVIDENCE_CREATED: StreamLayer.TOOL,
    ResearchEventType.CONTRADICTION_DETECTED: StreamLayer.TOOL,
    ResearchEventType.BUDGET_UPDATED: StreamLayer.ORCHESTRATOR,
    ResearchEventType.CONTEXT_COMPACTED: StreamLayer.ORCHESTRATOR,
}


def layer_for(event_type: ResearchEventType | str) -> StreamLayer:
    if not isinstance(event_type, ResearchEventType):
        try:
            event_type = ResearchEventType(event_type)
        except ValueError:
            return StreamLayer.ORCHESTRATOR
    return EVENT_LAYER.get(event_type, StreamLayer.ORCHESTRATOR)


def llm_token_stream_visible(role: AgentRole) -> bool:
    """Internal structured/verification tokens are never user-visible.

    Final report/synthesis token streaming is optional and currently off:
    partial model text is not Evidence.
    """
    del role
    return False


def subagent_streaming_enabled(*, max_delegation_depth: int) -> bool:
    """Nested LangGraph subgraph streams stay gated with max_depth > 1."""
    return max_delegation_depth > 1
