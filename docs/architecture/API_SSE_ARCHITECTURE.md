# API / SSE Architecture

## REST endpoints (Phase 6+)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/research/runs` | Start research run |
| `GET` | `/api/v1/research/runs/{id}` | Run status + summary |
| `GET` | `/api/v1/research/runs/{id}/stream` | SSE progress stream |
| `GET` | `/api/v1/research/runs/{id}/report` | Final report |

## SSE event types

| Event | Payload |
|---|---|
| `run.started` | run_id, goal, budget |
| `phase.started` | phase name, iteration |
| `phase.progress` | operational message (no CoT) |
| `source.collected` | source metadata |
| `claim.extracted` | claim summary + verification state |
| `contradiction.detected` | contradiction summary |
| `decision.ready` | decision preview |
| `report.ready` | report URL/id |
| `run.failed` | error code (no secrets) |
| `run.completed` | summary stats |

## Security

- No API keys in responses
- No raw LLM reasoning in SSE payloads
- CSRF protection when session auth is added
- Rate limiting via Redis (Phase 6+)

## Frontend consumption

Next.js EventSource client in `apps/web/` (Phase 7+).
