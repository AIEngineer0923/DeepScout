"""Budget/usage: failed attempts do not invent zero cost; success records once."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from deepscout_core.domain.enums import AgentRole, ResearchPhase
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.retry import RetryPolicy, run_with_retry
from deepscout_research.routing.model_router import ModelSelection
from deepscout_research.usage.recorder import record_model_usage
from langchain_core.messages import AIMessage


def test_failed_retries_do_not_record_usage() -> None:
    store = MagicMock()
    calls = {"n": 0}

    def flaky() -> AIMessage:
        calls["n"] += 1
        raise ConnectionError("down")

    try:
        run_with_retry(flaky, policy=RetryPolicy(max_attempts=3, base_delay_s=0.01, jitter=False))
    except ConnectionError:
        pass

    assert calls["n"] == 3
    store.record_token_usage.assert_not_called()
    # Failed attempts: usage UNKNOWN (not recorded as 0).


def test_successful_invoke_records_once_after_retries() -> None:
    store = MagicMock()
    settings = Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)
    selection = ModelSelection(
        provider=ProviderKind.GOOGLE,
        model="gemini-3.7-flash",
        agent_role=AgentRole.PLANNER,
    )
    calls = {"n": 0}

    def flaky() -> AIMessage:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("transient")
        return AIMessage(
            content="ok",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )

    message = run_with_retry(
        flaky, policy=RetryPolicy(max_attempts=3, base_delay_s=0.01, jitter=False)
    )
    record_model_usage(
        store,
        settings,
        message=message,
        run_id=uuid4(),
        phase=ResearchPhase.PLAN,
        role=AgentRole.PLANNER,
        selection=selection,
    )
    assert calls["n"] == 2
    assert store.record_token_usage.call_count == 1
