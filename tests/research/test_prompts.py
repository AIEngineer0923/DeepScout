from deepscout_research.prompts import PLANNER_V1, compose_system_message, get_prompt
from deepscout_research.prompts.spec import PromptStatus


def test_prompt_registry_contains_planner() -> None:
    spec = get_prompt("planner")
    assert spec.prompt_id == "planner"
    assert spec.prompt_version == "1"
    assert spec.status == PromptStatus.ACTIVE


def test_compose_system_message_layers() -> None:
    message = compose_system_message(PLANNER_V1, provider="google")
    assert "untrusted DATA" in message
    assert "Input contract:" in message
    assert "Output contract:" in message
    assert PLANNER_V1.instructions in message
    assert "Provider note:" in message


def test_trace_metadata_includes_status() -> None:
    meta = PLANNER_V1.trace_metadata()
    assert meta["prompt_id"] == "planner"
    assert meta["prompt_status"] == "active"
