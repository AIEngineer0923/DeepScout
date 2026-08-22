# Public instance and demo

## Hosted app (MODE B)

| | |
|---|---|
| URL | https://deep-scout-plum.vercel.app |
| Sign in | https://deep-scout-plum.vercel.app/login |
| Account / BYOK | https://deep-scout-plum.vercel.app/account |

### What you need

1. **GitHub account** — primary sign-in on the public instance (Google when configured by the operator).
2. **Your own provider keys** — Gemini, OpenAI, Anthropic, and/or Tavily in Account settings. DeepScout does not supply model quota for your research.
3. **Understanding of provider billing** — research consumes your API keys' quotas. The hosted frontend/worker hosting is separate from Google/OpenAI/Anthropic/Tavily charges.

### Typical flow

1. Sign in → Account → paste API keys (stored encrypted server-side; not shown again after save).
2. New Research → choose Quick / Standard / Deep, language, optional model hints.
3. Wait for run to complete (worker executes in background).
4. Browse Plan, Sources, Claims, Report, Evaluations.

### Privacy

- Runs belong to your principal; other users cannot list or open them.
- Optional LangSmith tracing uses **your** key if you enable it.
- See [providers.md](providers.md) and [SECURITY.md](../SECURITY.md).

## Explore Demo (no signup)

| | |
|---|---|
| URL | https://deep-scout-plum.vercel.app/demo |

Five **completed** research runs, read-only:

| Slug | Topic |
|------|-------|
| `rag-architecture-2026` | Hybrid RAG vs GraphRAG vs long-context (2026) |
| `multi-hop-research` | Multi-hop EU institutional research |
| `ev-battery-evidence` | LFP vs NMC for passenger EVs |
| `eu-ai-act-gpai-2026` | EU AI Act GPAI obligations |
| `ev-lifecycle-evidence` | EV lifecycle GHG under uncertainty |

### Demo guarantees (verified behavior)

- No signup required
- No provider/model calls while browsing demo pages
- Evaluation results are pre-persisted deterministic rows
- Mutations (new research, pin/exclude, etc.) are blocked for anonymous users

## Reference deployment architecture

The public instance uses:

- **Vercel** — Next.js frontend
- **Railway** — API + worker (same Docker image, different `DEEPSCOUT_PROCESS_ROLE`)
- **Managed PostgreSQL** — Supabase in the reference setup

This is a reference layout, not a hard requirement. See [DEPLOYMENT.md](DEPLOYMENT.md) to self-host elsewhere.
