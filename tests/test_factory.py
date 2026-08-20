from unittest.mock import MagicMock, patch

import pytest
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_providers.config import ModelBuildOptions
from deepscout_providers.factory import build_chat_model, build_embeddings
from pydantic import SecretStr


def test_build_chat_model_requires_api_key() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        GOOGLE_API_KEY=None,
    )
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        build_chat_model(settings)


def test_build_embeddings_openai_provider_requires_key() -> None:
    settings = Settings(
        _env_file=None,
        EMBEDDING_PROVIDER=ProviderKind.OPENAI,
        OPENAI_API_KEY=None,
    )
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_embeddings(settings)


@patch("langchain_google_genai.ChatGoogleGenerativeAI")
def test_google_factory_uses_provider_neutral_config(mock_chat: MagicMock) -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        GOOGLE_API_KEY=SecretStr("test-google-key"),
    )
    options = ModelBuildOptions(timeout=30.0, max_retries=3)

    build_chat_model(settings, options=options)

    mock_chat.assert_called_once()
    kwargs = mock_chat.call_args.kwargs
    assert kwargs["model"] == "gemini-3.7-flash"
    assert kwargs["google_api_key"] == "test-google-key"
    assert kwargs["timeout"] == 30.0
    assert kwargs["max_retries"] == 3
    assert "temperature" not in kwargs
    assert "thinking_level" not in kwargs
    assert "reasoning_effort" not in kwargs
    assert "thinking_budget" not in kwargs


@patch("langchain_openai.ChatOpenAI")
def test_openai_factory_uses_provider_neutral_config(mock_chat: MagicMock) -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.OPENAI,
        OPENAI_API_KEY=SecretStr("test-openai-key"),
    )

    build_chat_model(settings)

    kwargs = mock_chat.call_args.kwargs
    assert kwargs["model"] == "gpt-4.1-mini"
    assert kwargs["api_key"] == "test-openai-key"
    assert "temperature" not in kwargs


@patch("langchain_anthropic.ChatAnthropic")
def test_anthropic_factory_uses_provider_neutral_config(mock_chat: MagicMock) -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.ANTHROPIC,
        ANTHROPIC_API_KEY=SecretStr("test-anthropic-key"),
    )

    build_chat_model(settings)

    kwargs = mock_chat.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert kwargs["api_key"] == "test-anthropic-key"
    assert "temperature" not in kwargs
