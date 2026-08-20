from unittest.mock import MagicMock, patch

from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.smoke_agent import run_smoke_agent
from langchain_core.messages import AIMessage, ToolMessage


@patch("deepscout_research.smoke_agent.create_agent")
def test_run_smoke_agent_returns_structured_response(mock_create_agent: MagicMock) -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, LLM_MODEL="test-model")
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
            ToolMessage(content="research pipeline ready", tool_call_id="1"),
            AIMessage(content="Smoke path verified"),
        ]
    }
    mock_create_agent.return_value = mock_agent

    result = run_smoke_agent(
        settings,
        user_message="Verify DeepScout",
        chat_model=MagicMock(),
    )

    assert result.structured.reply == "Smoke path verified"
    assert result.structured.tool_used is True
    assert result.provider == "google"
    assert result.model == "test-model"
    mock_create_agent.assert_called_once()
