# Providers and API keys

How DeepScout uses LLM and search credentials.

## MODE A (local / self-host operator)

You put provider keys in `.env` on the machine running the API and worker:

- `GOOGLE_API_KEY`, `OPENAI_API_KEY`, and/or `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY` for web search

Keys stay on the server filesystem. There is no login; anyone who can reach the API can spend these keys — keep MODE A on `127.0.0.1` or a trusted network.

## MODE B (hosted — BYOK)

Signed-in users configure their own keys in **Account** settings. Supported vault providers include Gemini, OpenAI, Anthropic, and Tavily (see `CredentialProvider` in code).

### What happens when a user saves a key

1. Browser sends the key to the API over HTTPS (one time).
2. API encrypts with **AES-GCM** (`libs/research/.../credentials/vault.py`) using `CREDENTIAL_ENCRYPTION_KEY`.
3. Ciphertext + nonce stored in Postgres, bound to `principal_id` and provider.
4. API **never returns** the plaintext key to the frontend after save.
5. Worker/API decrypts only in memory for the duration of a provider call.

### Who can read keys

- The running API/worker process (needs `CREDENTIAL_ENCRYPTION_KEY`).
- Database administrators (ciphertext at rest — not end-to-end encrypted).
- **Not** other users (tenant isolation on runs and vault rows).
- **Not** anonymous demo visitors.

### Rotation and deletion

Users can update or remove keys in Account settings. Replacing a key re-encrypts with the current master key version.

### Maintainer keys

On hosted production, maintainer environment LLM keys are **not** used for user research runs. Demo browsing is read-only and does not invoke providers.

## Provider selection during research

- User can pick automatic model routing or explicit model hints on the New Research screen.
- Per-run `llm_provider` / `llm_model` stored on `research_runs`.
- Factory: `libs/providers/src/deepscout_providers/factory.py`.

## Cost implications

DeepScout tracks token/tool usage per run where providers return usage metadata. **Provider billing is between the user and Google/OpenAI/Anthropic/Tavily.** The public hosted instance does not charge for DeepScout itself; research still consumes the user's API quotas.

## Optional: LangSmith

If a user enables tracing with their own LangSmith key, research text may be sent to **their** LangSmith project. See [LANGSMITH_PRIVACY.md](architecture/LANGSMITH_PRIVACY.md).

## Security notes

- Do not log request bodies containing keys.
- `scripts/scan-secrets.sh` blocks common secret patterns in commits.
- Report exposure via [SECURITY.md](../SECURITY.md) (rotate the key regardless).
