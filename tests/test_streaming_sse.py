"""SSE framing and LLM-token streaming policy tests — no providers."""

from deepscout_core.domain.enums import AgentRole
from deepscout_core.domain.events import ResearchEventType
from deepscout_research.streaming.policy import (
    AUTHORITATIVE_EVENT_TYPES,
    layer_for,
    llm_token_stream_visible,
    subagent_streaming_enabled,
)
from deepscout_research.streaming.sse import format_sse_event, parse_last_event_id


def test_parse_last_event_id_prefers_query() -> None:
    assert parse_last_event_id("9", 3) == 3
    assert parse_last_event_id("9", None) == 9
    assert parse_last_event_id("nope", None) == 0


def test_sse_frame_includes_id_not_named_event() -> None:
    frame = format_sse_event(
        sequence=4,
        event_type="run.started",
        payload={"sequence": 4, "type": "run.started"},
    )
    assert frame.startswith("id: 4\n")
    assert "event: run.started" not in frame
    assert frame.endswith("\n\n")


def test_hitl_and_terminal_events_are_authoritative() -> None:
    assert ResearchEventType.RUN_PAUSED in AUTHORITATIVE_EVENT_TYPES
    assert ResearchEventType.REVIEW_REQUESTED in AUTHORITATIVE_EVENT_TYPES
    assert layer_for("worker.started").value == "worker"
    assert layer_for("source.discovered").value == "tool"


def test_llm_tokens_are_not_user_visible() -> None:
    for role in AgentRole:
        assert llm_token_stream_visible(role) is False
    assert subagent_streaming_enabled(max_delegation_depth=1) is False
    assert subagent_streaming_enabled(max_delegation_depth=2) is True
