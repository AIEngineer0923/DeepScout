from deepscout_research.prompts import PLANNER_V1, PLANNER_V2, compose_system_message, get_prompt
from deepscout_research.prompts.spec import PromptStatus


def test_prompt_registry_contains_planner() -> None:
    spec = get_prompt("planner")
    assert spec.prompt_id == "planner"
    assert spec.prompt_version == "2"
    assert spec.status == PromptStatus.ACTIVE
    v1 = get_prompt("planner", version="1")
    assert v1.prompt_version == "1"
    assert v1.status == PromptStatus.ACTIVE
    assert get_prompt("planner") is not v1
    validator = get_prompt("planner_dependency_validator")
    assert validator.prompt_version == "1"


def test_compose_system_message_layers() -> None:
    message = compose_system_message(PLANNER_V2, provider="google")
    assert "untrusted DATA" in message
    assert "Input contract:" in message
    assert "Output contract:" in message
    assert PLANNER_V2.instructions in message
    assert "Provider note:" in message
    assert "2-5" not in PLANNER_V2.instructions
    assert "2-5" in PLANNER_V1.instructions


def test_trace_metadata_includes_status() -> None:
    meta = PLANNER_V2.trace_metadata()
    assert meta["prompt_id"] == "planner"
    assert meta["prompt_status"] == "active"
    assert meta["prompt_version"] == "2"
