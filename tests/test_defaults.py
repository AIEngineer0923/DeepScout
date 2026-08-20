from deepscout_core.types import ProviderKind
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS, DEFAULT_EMBEDDING_MODELS


def test_default_chat_models_are_stable_ids() -> None:
    assert DEFAULT_CHAT_MODELS[ProviderKind.GOOGLE] == "gemini-3.7-flash"
    assert DEFAULT_CHAT_MODELS[ProviderKind.OPENAI] == "gpt-4.1-mini"
    assert DEFAULT_CHAT_MODELS[ProviderKind.ANTHROPIC] == "claude-haiku-4-5-20251001"


def test_default_embedding_models_present_for_each_provider() -> None:
    for provider in ProviderKind:
        assert provider in DEFAULT_EMBEDDING_MODELS
        assert DEFAULT_EMBEDDING_MODELS[provider]


def test_google_embedding_default_is_stable_ga_model() -> None:
    assert DEFAULT_EMBEDDING_MODELS[ProviderKind.GOOGLE] == "gemini-embedding-2"
