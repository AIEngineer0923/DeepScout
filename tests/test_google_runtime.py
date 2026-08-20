"""Live Google runtime verification — runs only when local .env has GOOGLE_API_KEY."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_providers.factory import build_chat_model
from deepscout_research.smoke_agent import (
    SmokeAgentResponse,
    SmokeAgentResult,
    confirm_research_ready,
)
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

_FORBIDDEN_TRACE_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"lsv2_[a-zA-Z0-9]{10,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"sk-ant-[a-zA-Z0-9-]{20,}"),
    re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
    re.compile("/" + "Users" + r"/[^/]+/"),
    re.compile(r"GOOGLE_API_KEY"),
    re.compile(r"LANGSMITH_API_KEY"),
    re.compile(r"postgresql\+psycopg://"),
    re.compile(r"redis://[^\s]+@"),
    re.compile(r"Agent OS|IAF-Agent|\.agents/"),
)


@dataclass(frozen=True)
class SmokeRuntimeEvidence:
    response: SmokeAgentResponse
    message_sequence: list[str]
    runtime_model: str


def _google_runtime_configured() -> bool:
    settings = Settings()
    return settings.google_api_key is not None


def _assert_no_forbidden_trace_content(payload: object) -> None:
    serialized = json.dumps(payload, default=str)
    for pattern in _FORBIDDEN_TRACE_PATTERNS:
        assert not pattern.search(serialized), f"Forbidden trace content matched: {pattern.pattern}"


def _message_sequence_labels(messages: list[object]) -> list[str]:
    labels: list[str] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            labels.append("HumanMessage")
        elif isinstance(message, AIMessage):
            labels.append("AIMessage(tool_call)" if message.tool_calls else "AIMessage(final)")
        elif isinstance(message, ToolMessage):
            labels.append("ToolMessage")
        else:
            labels.append(type(message).__name__)
    return labels


def _run_single_smoke_invocation(settings: Settings, user_message: str) -> SmokeRuntimeEvidence:
    chat_model = build_chat_model(settings)
    runtime_model = getattr(chat_model, "model", None) or getattr(chat_model, "model_name", None)
    assert runtime_model is not None

    agent = create_agent(
        model=chat_model,
        tools=[confirm_research_ready],
        system_prompt=(
            "You are DeepScout smoke test agent. "
            "Always call confirm_research_ready with the user's topic, then answer briefly."
        ),
    )
    invoke_result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
    messages = invoke_result["messages"]
    final = messages[-1]
    reply = final.content if isinstance(final, AIMessage) else str(final.content)
    tool_used = any(isinstance(message, ToolMessage) for message in messages)

    response = SmokeAgentResponse(
        structured=SmokeAgentResult(reply=str(reply), tool_used=tool_used),
        provider=settings.llm_provider.value,
        model=str(runtime_model),
    )
    return SmokeRuntimeEvidence(
        response=response,
        message_sequence=_message_sequence_labels(messages),
        runtime_model=str(runtime_model),
    )


def _recent_langsmith_runs(
    client: object,
    *,
    project_name: str,
    started_before: datetime,
    limit: int = 20,
) -> list[object]:
    runs = list(client.list_runs(project_name=project_name, limit=limit))  # type: ignore[attr-defined]
    recent = []
    for run in runs:
        if not run.start_time:
            continue
        run_start = run.start_time
        if run_start.tzinfo is None:
            run_start = run_start.replace(tzinfo=UTC)
        if run_start >= started_before:
            recent.append(run)
    return recent


pytestmark = pytest.mark.skipif(
    not _google_runtime_configured(),
    reason="GOOGLE_API_KEY required for live Google runtime verification",
)


@pytest.mark.integration
def test_real_google_runtime_tool_call_langsmith_trace_and_privacy() -> None:
    settings = Settings()
    assert settings.llm_provider == ProviderKind.GOOGLE

    if settings.langsmith_api_key is None:
        pytest.skip("LANGSMITH_API_KEY required for live trace verification")
    if not settings.langsmith_workspace_id:
        pytest.fail(
            "LANGSMITH_WORKSPACE_ID is required for organization-scoped LangSmith keys. "
            "Add it from LangSmith Settings > General > Workspace ID."
        )

    from langsmith import Client

    configure_observability = __import__(
        "deepscout_api.main", fromlist=["configure_observability"]
    ).configure_observability
    configure_observability(settings)

    client = Client(
        api_url=settings.langsmith_endpoint,
        workspace_id=settings.langsmith_workspace_id,
    )
    started_before = datetime.now(UTC) - timedelta(seconds=10)

    evidence = _run_single_smoke_invocation(
        settings,
        user_message="One short sentence about weather research.",
    )

    assert evidence.runtime_model == "gemini-3.7-flash"
    assert evidence.response.model == "gemini-3.7-flash"
    assert evidence.response.provider == "google"
    assert evidence.response.structured.tool_used is True
    assert evidence.response.structured.reply.strip()
    assert evidence.message_sequence == [
        "HumanMessage",
        "AIMessage(tool_call)",
        "ToolMessage",
        "AIMessage(final)",
    ]

    time.sleep(3.0)
    deadline = time.time() + 45.0
    root_run = None
    while time.time() < deadline:
        recent = _recent_langsmith_runs(
            client,
            project_name=settings.langsmith_project,
            started_before=started_before,
        )
        if recent:
            root_run = max(recent, key=lambda run: run.start_time or started_before)
            break
        time.sleep(2.0)

    assert root_run is not None, f"No LangSmith runs found in project {settings.langsmith_project}"

    trace_id = root_run.trace_id or root_run.id
    child_runs = list(client.list_runs(project_name=settings.langsmith_project, trace_id=trace_id))
    observed_runs = [root_run, *child_runs]
    run_types = {run.run_type for run in observed_runs if run.run_type}
    assert run_types.intersection({"tool", "llm", "chain"}), (
        f"Expected model/tool activity in trace, got run types: {sorted(run_types)}"
    )

    for run in observed_runs:
        _assert_no_forbidden_trace_content(
            {
                "name": run.name,
                "run_type": run.run_type,
                "status": run.status,
                "extra": run.extra,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "serialized": run.serialized,
            }
        )

    assert root_run.end_time is not None or root_run.status in {"success", "pending", "running"}
