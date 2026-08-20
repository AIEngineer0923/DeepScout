from dataclasses import dataclass

from deepscout_core.settings import Settings
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS
from deepscout_providers.factory import build_chat_model
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field


class SmokeAgentResult(BaseModel):
    """Structured result from the smoke agent path."""

    reply: str = Field(description="Final assistant message text")
    tool_used: bool = Field(description="Whether the agent invoked the smoke tool")


@dataclass(frozen=True)
class SmokeAgentResponse:
    structured: SmokeAgentResult
    provider: str
    model: str


@tool
def confirm_research_ready(topic: str) -> str:
    """Confirm DeepScout research tooling is reachable for a topic."""
    return f"research pipeline ready for topic: {topic}"


def _runtime_model_name(settings: Settings, chat_model: BaseChatModel) -> str:
    if settings.llm_model:
        return settings.llm_model
    runtime_model = getattr(chat_model, "model", None) or getattr(chat_model, "model_name", None)
    if runtime_model:
        return str(runtime_model)
    return DEFAULT_CHAT_MODELS[settings.llm_provider]


def run_smoke_agent(
    settings: Settings,
    *,
    user_message: str,
    chat_model: BaseChatModel | None = None,
) -> SmokeAgentResponse:
    """Run a minimal LangChain agent loop with one tool (smoke/integration test)."""
    model = chat_model or build_chat_model(settings)
    model_name = _runtime_model_name(settings, model)

    agent = create_agent(
        model=model,
        tools=[confirm_research_ready],
        system_prompt=(
            "You are DeepScout smoke test agent. "
            "Always call confirm_research_ready with the user's topic, then answer briefly."
        ),
    )

    result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
    messages = result["messages"]
    final = messages[-1]
    reply = final.content if isinstance(final, AIMessage) else str(final.content)
    tool_used = any(isinstance(message, ToolMessage) for message in messages)

    return SmokeAgentResponse(
        structured=SmokeAgentResult(reply=str(reply), tool_used=tool_used),
        provider=settings.llm_provider.value,
        model=model_name,
    )
