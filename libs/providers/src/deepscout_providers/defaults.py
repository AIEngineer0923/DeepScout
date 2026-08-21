"""Centralized model identifiers.

Verified against official documentation (20 August 2026):
- Google Gemini API chat: https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash
  (GA 13 August 2026; latest Flash for agentic/coding workflows)
- Google Gemini API embeddings: https://ai.google.dev/gemini-api/docs/embeddings
  (`gemini-embedding-2` recommended replacement for `gemini-embedding-001`)
- OpenAI API models: https://developers.openai.com/api/docs/models
- Anthropic models: https://docs.anthropic.com/en/docs/about-claude/models
- LangChain integrations: https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
"""

from deepscout_core.types import ProviderKind

# Chat models — override via LLM_MODEL env var
DEFAULT_CHAT_MODELS: dict[ProviderKind, str] = {
    ProviderKind.GOOGLE: "gemini-3.7-flash",
    ProviderKind.OPENAI: "gpt-4.1-mini",
    ProviderKind.ANTHROPIC: "claude-haiku-4-5-20251001",
}

# Embedding models — override via EMBEDDING_MODEL env var.
# Anthropic has no embedding API (confirmed 2026-08-21); chat-only.
DEFAULT_EMBEDDING_MODELS: dict[ProviderKind, str] = {
    ProviderKind.GOOGLE: "gemini-embedding-2",
    ProviderKind.OPENAI: "text-embedding-3-small",
}
