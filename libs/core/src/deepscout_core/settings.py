from typing import TYPE_CHECKING

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from deepscout_core.types import ProviderKind

if TYPE_CHECKING:
    from deepscout_core.domain.budget import ResearchBudget


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    enable_smoke_agent: bool = Field(default=False, alias="ENABLE_SMOKE_AGENT")
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")
    rate_limit_max_requests: int = Field(default=120, alias="RATE_LIMIT_MAX_REQUESTS")
    rate_limit_mutating_max: int = Field(default=20, alias="RATE_LIMIT_MUTATING_MAX")
    rate_limit_window_s: int = Field(default=60, alias="RATE_LIMIT_WINDOW_S")
    max_request_bytes: int = Field(default=1_000_000, alias="MAX_REQUEST_BYTES")

    llm_provider: ProviderKind = Field(default=ProviderKind.GOOGLE, alias="LLM_PROVIDER")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    embedding_provider: ProviderKind | None = Field(default=None, alias="EMBEDDING_PROVIDER")
    embedding_model: str | None = Field(default=None, alias="EMBEDDING_MODEL")

    google_api_key: SecretStr | None = Field(default=None, alias="GOOGLE_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    tavily_api_key: SecretStr | None = Field(default=None, alias="TAVILY_API_KEY")

    langsmith_tracing: bool = Field(default=True, alias="LANGSMITH_TRACING")
    langsmith_api_key: SecretStr | None = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="deepscout-dev", alias="LANGSMITH_PROJECT")
    langsmith_workspace_id: str | None = Field(default=None, alias="LANGSMITH_WORKSPACE_ID")
    langsmith_endpoint: str | None = Field(default=None, alias="LANGSMITH_ENDPOINT")

    database_url: str = Field(
        default="postgresql+psycopg://deepscout:deepscout@localhost:5432/deepscout",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    research_max_iterations: int = Field(default=5, alias="RESEARCH_MAX_ITERATIONS")
    research_max_wall_time_s: int = Field(default=900, alias="RESEARCH_MAX_WALL_TIME_S")
    research_max_sources: int = Field(default=40, alias="RESEARCH_MAX_SOURCES")
    research_max_tool_calls: int = Field(default=80, alias="RESEARCH_MAX_TOOL_CALLS")
    research_workers_inline: bool = Field(default=False, alias="RESEARCH_WORKERS_INLINE")
    research_use_legacy_path: bool = Field(default=False, alias="RESEARCH_USE_LEGACY_PATH")
    research_durable_langgraph_checkpoint: bool = Field(
        default=True,
        alias="RESEARCH_DURABLE_LANGGRAPH_CHECKPOINT",
    )
    research_task_stale_after_s: int = Field(default=180, alias="RESEARCH_TASK_STALE_AFTER_S")
    research_finalize_on_budget_exhausted: bool = Field(
        default=True,
        alias="RESEARCH_FINALIZE_ON_BUDGET_EXHAUSTED",
    )
    llm_timeout_s: float = Field(default=60.0, alias="LLM_TIMEOUT_S")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")

    def default_research_budget(self) -> "ResearchBudget":
        from deepscout_core.domain.budget import ResearchBudget

        return ResearchBudget(
            max_iterations=self.research_max_iterations,
            max_wall_time_seconds=self.research_max_wall_time_s,
            max_sources=self.research_max_sources,
            max_tool_calls=self.research_max_tool_calls,
        )

    def resolved_embedding_provider(self) -> ProviderKind:
        return self.embedding_provider or self.llm_provider

    def require_tavily_api_key(self) -> str:
        if self.tavily_api_key is None:
            raise ValueError("TAVILY_API_KEY is required for web search")
        return self.tavily_api_key.get_secret_value()

    def require_api_key(self, provider: ProviderKind) -> str:
        match provider:
            case ProviderKind.GOOGLE:
                if self.google_api_key is None:
                    raise ValueError("GOOGLE_API_KEY is required for Google provider")
                return self.google_api_key.get_secret_value()
            case ProviderKind.OPENAI:
                if self.openai_api_key is None:
                    raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
                return self.openai_api_key.get_secret_value()
            case ProviderKind.ANTHROPIC:
                if self.anthropic_api_key is None:
                    raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
                return self.anthropic_api_key.get_secret_value()


def get_settings() -> Settings:
    return Settings()
