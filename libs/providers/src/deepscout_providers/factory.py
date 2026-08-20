from typing import Any

from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from deepscout_providers.config import DEFAULT_MODEL_BUILD_OPTIONS, ModelBuildOptions
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS, DEFAULT_EMBEDDING_MODELS


def _apply_build_options(kwargs: dict[str, Any], options: ModelBuildOptions) -> dict[str, Any]:
    if options.timeout is not None:
        kwargs["timeout"] = options.timeout
    if options.max_retries is not None:
        kwargs["max_retries"] = options.max_retries
    return kwargs


def _build_google_chat_model(
    *,
    model_name: str,
    settings: Settings,
    options: ModelBuildOptions,
) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {
        "model": model_name,
        "google_api_key": settings.require_api_key(ProviderKind.GOOGLE),
    }
    # Gemini 3.7 uses thinking levels (default: medium). Do not pass temperature or
    # thinking_level here — let the model and LangChain integration apply defaults.
    return ChatGoogleGenerativeAI(**_apply_build_options(kwargs, options))


def _build_openai_chat_model(
    *,
    model_name: str,
    settings: Settings,
    options: ModelBuildOptions,
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": settings.require_api_key(ProviderKind.OPENAI),
    }
    return ChatOpenAI(**_apply_build_options(kwargs, options))


def _build_anthropic_chat_model(
    *,
    model_name: str,
    settings: Settings,
    options: ModelBuildOptions,
) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": settings.require_api_key(ProviderKind.ANTHROPIC),
    }
    return ChatAnthropic(**_apply_build_options(kwargs, options))


def build_chat_model(
    settings: Settings,
    *,
    options: ModelBuildOptions | None = None,
    provider: ProviderKind | None = None,
    model_name: str | None = None,
) -> BaseChatModel:
    """Return a LangChain chat model for the configured or overridden provider."""
    build_options = options or DEFAULT_MODEL_BUILD_OPTIONS
    resolved_provider = provider or settings.llm_provider
    resolved_model = model_name or settings.llm_model or DEFAULT_CHAT_MODELS[resolved_provider]
    match resolved_provider:
        case ProviderKind.GOOGLE:
            return _build_google_chat_model(
                model_name=resolved_model,
                settings=settings,
                options=build_options,
            )
        case ProviderKind.OPENAI:
            return _build_openai_chat_model(
                model_name=resolved_model,
                settings=settings,
                options=build_options,
            )
        case ProviderKind.ANTHROPIC:
            return _build_anthropic_chat_model(
                model_name=resolved_model,
                settings=settings,
                options=build_options,
            )


def build_embeddings(settings: Settings) -> Embeddings:
    """Return embeddings for the configured embedding provider."""
    provider = settings.resolved_embedding_provider()
    model_name = settings.embedding_model or DEFAULT_EMBEDDING_MODELS[provider]

    match provider:
        case ProviderKind.GOOGLE:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            return GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=settings.require_api_key(ProviderKind.GOOGLE),
            )
        case ProviderKind.OPENAI:
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model=model_name,
                api_key=settings.require_api_key(ProviderKind.OPENAI),
            )
        case ProviderKind.ANTHROPIC:
            raise ValueError(
                "Anthropic has no embedding API; set EMBEDDING_PROVIDER to google or openai"
            )
